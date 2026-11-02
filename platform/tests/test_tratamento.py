"""A aba Ficha Virtual: o tratamento ENTREGUE, e o portão que a segura.

O que se testa aqui é sobretudo o que a tela NÃO faz: não mostra número enquanto
o mapeamento das tabelas de tratamento não for conferido contra o banco real, e
não preenche "quem tratou" com nada quando o banco não diz quem tratou.

Rodar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import base64
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_dados as capa_dados_modulo  # noqa: E402
from isocentro.banco import capa_db as capa_db_modulo  # noqa: E402
from isocentro.dados import equipe  # noqa: E402
from isocentro.banco import tratamento_db  # noqa: E402

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QObject, QPoint, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import (QApplication, QDialog, QHeaderView,
                                 QLabel, QWidget)
    from isocentro.interface import tratamento
    _APP = QApplication.instance() or QApplication([])
except Exception:  # noqa: BLE001 — sem Qt, os testes de dado continuam valendo
    tratamento = None
    _APP = None
    Qt = None
    QEvent = None
    QObject = object
    QPoint = None
    QMouseEvent = None
    QHeaderView = None
    QDialog = None
    QWidget = None
    QLabel = None


def _clicar(w, dentro: bool = True) -> None:
    """Aperta e SOLTA o mouse sobre o widget, como a mão faz.

    Os cartões-porta desta aba agem no soltar (ver
    ``tratamento._ValorClicavel``), então mandar só o ``mousePressEvent`` — que
    é como estes testes faziam — deixaria de exercitar o gesto que existe.
    """
    ponto = w.rect().center() if dentro else QPoint(-40, -40)

    def evento(tipo):
        return QMouseEvent(tipo, ponto, Qt.LeftButton, Qt.LeftButton,
                           Qt.NoModifier)

    w.mousePressEvent(evento(QEvent.MouseButtonPress))
    w.mouseReleaseEvent(evento(QEvent.MouseButtonRelease))


def _sessao(dia: int, mes: int = 8, fracao: int = 1, **kw):
    return tratamento_db.Sessao(fracao=fracao, data=date(2026, mes, dia), **kw)


def _destruir(w) -> None:
    """Fecha E destrói o painel. ``close()`` sozinho não basta.

    Custou uma ordem aleatória inteira (semente 256002144): o painel não tem
    pai, então é uma JANELA DE TOPO, e o teste do botão "Trocar paciente" ainda
    chama ``setFocus`` nela. Fechada mas viva, ela continuava disputando o foco
    do processo, e o ``Ctrl+Tab`` de ``test_gui_smoke`` — que é um
    ``WindowShortcut`` — deixava de chegar à janela principal 90 testes depois.

    ``processEvents`` NÃO entrega ``DeferredDelete``; é preciso pedi-lo pelo
    nome (armadilha já catalogada no CLAUDE.md).
    """
    from PySide6.QtCore import QEvent
    w.close()
    w.setParent(None)
    w.deleteLater()
    _APP.sendPostedEvents(None, QEvent.DeferredDelete)
    _APP.processEvents()


class TestPortao(unittest.TestCase):
    """Sem mapeamento conferido, nada de número — nem plausível.

    O erro que este portão evita não é o barulhento (nome de coluna inventado,
    que estoura na hora): é ler "frações PLANEJADAS" achando que são
    "ENTREGUES". Isso devolve um número que parece certo, e é justamente o
    número que o médico lê grande no meio da tela.
    """

    def setUp(self):
        self._verificado = tratamento_db.VERIFICADO_EM

    def tearDown(self):
        tratamento_db.VERIFICADO_EM = self._verificado

    def test_aberto_com_a_data_da_conferencia(self):
        """O portão foi aberto em 19/08/2026, e as duas rodadas estão no NOTAS.

        Este teste nasceu exigindo o portão FECHADO; abri-lo obrigou a mudá-lo,
        que era o objetivo — a conferência não pode ser um commit silencioso.
        Agora ele guarda o outro lado: a data não pode ser apagada nem trocada
        por um "sim" solto, porque é ela que diz CONTRA QUANDO o banco foi
        conferido. Esquema de DW muda em atualização do ARIA.
        """
        self.assertRegex(tratamento_db.VERIFICADO_EM, r"^\d{2}/\d{2}/\d{4}$")

    def test_fechado_nao_consulta(self):
        tratamento_db.VERIFICADO_EM = ""
        self.assertFalse(tratamento_db.disponivel())
        self.assertEqual(tratamento_db.sessoes_do_paciente("9000001CEL"), [])
        self.assertIsNone(tratamento_db.tratamento_do_paciente("9000001CEL"))

    def test_motivo_distingue_banco_de_mapeamento(self):
        """Dois problemas diferentes, duas saídas diferentes.

        "Sem banco apontado" o admin resolve na tela de Configurações; "sem
        mapeamento conferido" é trabalho meu que não terminou. Um recado só para
        os dois mandaria metade das pessoas mexer no que não é.
        """
        tratamento_db.VERIFICADO_EM = ""
        motivo = tratamento_db.motivo_indisponivel()
        self.assertTrue(motivo)
        # Sem servidor configurado neste ambiente de teste, o recado é o do
        # banco — e é ele que tem de aparecer primeiro, porque é o resolvível.
        esperado = ("Serviço" if not _tem_banco() else "conferida")
        self.assertIn(esperado, motivo)


def _tem_banco() -> bool:
    from isocentro.banco import capa_db
    return capa_db.configurado()


class TestIntervalos(unittest.TestCase):
    """Faltas e paradas — a conta que roda sem banco nenhum."""

    def test_fim_de_semana_nao_e_parada(self):
        """Sexta → segunda são 3 dias de calendário e ZERO dias úteis.

        Contando corrido, todo paciente teria uma "parada" por semana e o aviso
        viraria ruído — aviso que sempre aparece deixa de ser lido.
        """
        sexta, segunda = date(2026, 8, 14), date(2026, 8, 17)
        self.assertEqual(sexta.weekday(), 4)
        self.assertEqual(tratamento_db.dias_uteis_entre(sexta, segunda), 0)

    def test_um_dia_perdido_aparece(self):
        seg, qua = date(2026, 8, 17), date(2026, 8, 19)
        self.assertEqual(tratamento_db.dias_uteis_entre(seg, qua), 1)

    def test_semana_inteira_parada(self):
        self.assertEqual(
            tratamento_db.dias_uteis_entre(date(2026, 8, 17), date(2026, 8, 25)),
            5)

    def test_duas_fracoes_no_mesmo_dia_nao_sao_intervalo(self):
        """Dois isocentros no mesmo turno não são uma parada de zero dias.

        Sem desduplicar as datas, o par (dia, dia) entrava na lista com
        ``dias_uteis=0`` e a tela mostrava "parada de 0 dias" — que não é coisa
        que exista.
        """
        sessoes = [_sessao(17, fracao=1), _sessao(17, fracao=2),
                   _sessao(18, fracao=3)]
        for i in tratamento_db.intervalos_das_sessoes(sessoes):
            self.assertGreater(i.dias_uteis, 0)

    def test_intervalos_vem_do_mais_recente(self):
        """Quem abre a tela quer a parada de agora, não a do mês passado."""
        sessoes = [_sessao(3), _sessao(5), _sessao(17), _sessao(19)]
        achados = tratamento_db.intervalos_das_sessoes(sessoes)
        self.assertTrue(achados)
        self.assertGreaterEqual(achados[0].de, achados[-1].de)

    def test_sessao_sem_data_nao_derruba_a_conta(self):
        """O DW tem linha com data nula; ignorá-la é melhor que explodir."""
        sessoes = [_sessao(17), tratamento_db.Sessao(fracao=2), _sessao(19)]
        self.assertEqual(len(tratamento_db.intervalos_das_sessoes(sessoes)), 1)


class TestPlanosQueTratamJuntos(unittest.TestCase):
    """Mama e FSC: dois planos no sistema, UMA sessão na sala.

    O que quebrou no uso (20/08/2026, paciente de mama replanejada): a tela
    mostrou **16 / 15**, encheu a barra e escreveu "tratamento concluído" numa
    paciente na 8ª sessão de 15. Cada dia gerava DUAS linhas — fração 7 do
    ``cFSC_D2`` às 10:42, fração 7 do ``cMAMA_BOOSTD2`` às 10:37 — e contar
    linhas dobrava o tratamento. Quem denunciou foi a dose entregue, que vem
    pronta do DW: 2240 cGy de 4800.
    """

    def _par(self, dia: int, hora_a="10:37", hora_b="10:42", fracao=1,
             pa=71, pb=72, previstas=15):
        """Um dia de mama + FSC: duas linhas, dois planos, a mesma fração."""
        return [_sessao(dia, fracao=fracao, plano=pa, plano_nome="cMAMA_D2",
                        hora=hora_a, plano_previstas=previstas),
                _sessao(dia, fracao=fracao, plano=pb, plano_nome="cFSC_D2",
                        hora=hora_b, plano_previstas=previstas)]

    def test_mama_e_fsc_no_mesmo_dia_sao_UMA_fracao(self):
        self.assertEqual(
            tratamento_db.fracoes_entregues(self._par(19) + self._par(20)), 2)

    def test_dois_turnos_do_MESMO_plano_continuam_duas_fracoes(self):
        """Dois isocentros no mesmo dia existem, e apagar o segundo seria o
        erro oposto — o que junta é o plano ser OUTRO, não o dia ser o mesmo."""
        duas = [_sessao(19, fracao=1, plano=71), _sessao(19, fracao=2, plano=71)]
        self.assertEqual(tratamento_db.fracoes_entregues(duas), 2)

    def test_planos_que_nunca_dividem_um_dia_nao_se_juntam(self):
        """Replanejar não é tratar junto: o plano velho PARA no dia em que o
        novo começa, e por isso os dois grupos saem separados."""
        velho = [_sessao(7, fracao=1, plano=71)]
        novo = [_sessao(20, fracao=2, plano=99), _sessao(19, fracao=1, plano=99)]
        grupos = tratamento_db.planos_simultaneos(novo + velho)
        self.assertEqual([sorted(g) for g in grupos], [[99], [71]])

    def test_o_grupo_de_AGORA_vem_primeiro(self):
        """A tela fala do plano em curso; o anterior é contexto."""
        sessoes = self._par(20, fracao=2) + self._par(19, fracao=1) \
            + [_sessao(7, fracao=1, plano=60, plano_nome="cMAMA_ANTIGO")]
        grupos = tratamento_db.planos_simultaneos(sessoes)
        self.assertEqual(len(grupos), 2)
        self.assertNotIn(60, grupos[0])
        self.assertEqual(grupos[-1], {60})

    def test_sessao_sem_data_conta_sozinha_em_vez_de_sumir(self):
        soltas = [tratamento_db.Sessao(fracao=1, plano=71)]
        self.assertEqual(tratamento_db.fracoes_entregues(soltas), 1)

    def test_nomes_do_grupo_na_ordem_da_SALA(self):
        """A mama entra às 10:37 e a fossa às 10:42. Em ordem alfabética o
        ``cFSC`` viria primeiro por acaso da letra, e o nome do plano é como o
        serviço fala do caso."""
        self.assertEqual(tratamento_db._nomes_do_grupo(self._par(20)),
                         "cMAMA_D2 + cFSC_D2")


class TestGruposDoCurso(unittest.TestCase):
    """Os grupos que o seletor de plano oferece.

    Nasceram do caso de 26/08/2026: um curso (`C1_JAN_2026`) com uma SBRT de
    pulmão (`sPTV_1` + `sPTV_2`) e, depois, uma mandíbula. O quadro mostrava
    "9 / 4" — as frações do CURSO divididas pelo total de UM plano.
    """

    def _curso_com_dois_tratamentos(self):
        sbrt = []
        for dia in (13, 11, 9, 6):
            sbrt += [_sessao(dia, mes=3, plano=91, plano_nome="sPTV_1",
                             hora="11:12", plano_previstas=4),
                     _sessao(dia, mes=3, plano=92, plano_nome="sPTV_2",
                             hora="11:24", plano_previstas=4)]
        mandibula = [_sessao(dia, mes=3, plano=90, plano_nome="sMANDIBULA_E",
                             hora="10:32", plano_previstas=5)
                     for dia in (27, 25, 23, 20, 18)]
        return tratamento_db.Tratamento(entregues=9, previstas=4,
                                        sessoes=mandibula + sbrt)

    def test_cada_tratamento_do_curso_vira_um_grupo(self):
        grupos = tratamento_db.grupos_do_curso(self._curso_com_dois_tratamentos())
        self.assertEqual([g.nome for g in grupos],
                         ["sMANDIBULA_E", "sPTV_1 + sPTV_2"])

    def test_o_grupo_conta_as_fracoes_DELE(self):
        """5 e 4 — e é a soma dos dois que dá o 9 do curso."""
        grupos = tratamento_db.grupos_do_curso(self._curso_com_dois_tratamentos())
        self.assertEqual([g.entregues for g in grupos], [5, 4])
        self.assertEqual([g.previstas for g in grupos], [5, 4])

    def test_os_dois_planos_que_tratam_juntos_sao_UM_grupo(self):
        """O que o seletor oferece é o GRUPO, não o plano: mama e FSC são uma
        sessão só para quem deita na mesa, e duas opções ali seriam duas
        respostas para a mesma pergunta."""
        grupos = tratamento_db.grupos_do_curso(self._curso_com_dois_tratamentos())
        self.assertEqual(grupos[1].planos, (91, 92))
        self.assertEqual(grupos[1].entregues, 4)

    def test_o_grupo_em_curso_e_o_primeiro(self):
        grupos = tratamento_db.grupos_do_curso(self._curso_com_dois_tratamentos())
        self.assertTrue(grupos[0].atual)
        self.assertFalse(grupos[1].atual)

    def test_o_rotulo_traz_o_periodo_e_a_contagem(self):
        """É o número que faz escolher entre um item e outro da lista.

        Ao contrário do seletor de CURSOS, onde a contagem saiu por vir de outra
        consulta que a do número grande: aqui as duas saem das MESMAS sessões
        que a tela já tem na mão.
        """
        g = tratamento_db.grupos_do_curso(
            self._curso_com_dois_tratamentos())[1]
        self.assertIn("sPTV_1 + sPTV_2", g.rotulo())
        self.assertIn("06/03/2026", g.rotulo())
        self.assertIn("13/03/2026", g.rotulo())
        self.assertIn("4 de 4", g.rotulo())

    def test_curso_sem_sessao_nao_tem_grupo(self):
        """Sem sessão não há plano a nomear — e seletor de item nenhum é uma
        caixa vazia prometendo escolha."""
        self.assertEqual(
            tratamento_db.grupos_do_curso(tratamento_db.Tratamento()), [])

    def test_total_que_nao_cobre_o_aplicado_nao_e_total_do_curso(self):
        """O "4" do DW é de um plano; as 9 frações são do curso."""
        t = self._curso_com_dois_tratamentos()
        self.assertFalse(t.total_confere())

    def test_total_que_cobre_continua_valendo(self):
        """O replanejamento de verdade: 30 previstas, 21 aplicadas, e o DW sabe
        que o plano novo SUBSTITUI o que restava do velho."""
        t = tratamento_db.Tratamento(entregues=21, previstas=30)
        self.assertTrue(t.total_confere())

    def test_sem_total_nao_ha_divisao_para_estar_errada(self):
        """Zero previstas é o outro caso — "o sistema não informou" —, e ele
        tem recado próprio na tela."""
        self.assertTrue(tratamento_db.Tratamento(entregues=9).total_confere())


class TestQuadroComPlanosSimultaneos(unittest.TestCase):
    """O quadro montado de ponta a ponta — era ali que a conta dobrava.

    ``tratamento_do_paciente`` é quem soma as sessões; testar só as funções
    soltas deixaria de fora justamente a linha que estava errada
    (``entregues=len(sessoes)``).
    """

    def setUp(self):
        self._guardado = {
            n: getattr(tratamento_db, n)
            for n in ("disponivel", "cursos_do_paciente", "sessoes_do_paciente",
                      "resumo_do_curso", "medico_do_paciente")}

    def tearDown(self):
        # DEVOLVER, nunca ``del``: ``del modulo.f`` apaga a função ORIGINAL do
        # módulo para o resto do processo (armadilha catalogada no CLAUDE.md).
        for nome, fn in self._guardado.items():
            setattr(tratamento_db, nome, fn)

    def _quadro(self, sessoes, previstas=15, dose=2240.0):
        curso = tratamento_db.Curso(id=1, nome="C1", atual=True)
        tratamento_db.disponivel = lambda: True
        tratamento_db.cursos_do_paciente = lambda *_a, **_k: [curso]
        tratamento_db.sessoes_do_paciente = lambda *_a, **_k: sessoes
        tratamento_db.resumo_do_curso = lambda *_a, **_k: (0, previstas,
                                                           dose, 4800.0)
        tratamento_db.medico_do_paciente = lambda *_a, **_k: ""
        return tratamento_db.tratamento_do_paciente("9000013CEL")

    def _mama_com_fsc(self):
        """A paciente de 20/08: um dia com o par ANTIGO, sete com o novo."""
        sessoes = []
        for i, dia in enumerate([20, 19, 18, 17, 14, 13, 12]):
            fr = 7 - i
            sessoes += [
                _sessao(dia, fracao=fr, plano=72, plano_nome="cMAMA_BOOSTD2",
                        hora="10:37", plano_previstas=15),
                _sessao(dia, fracao=fr, plano=73, plano_nome="cFSC_D2",
                        hora="10:42", plano_previstas=15)]
        sessoes += [
            _sessao(7, fracao=1, plano=70, plano_nome="cMAMA_D2", hora="09:10"),
            _sessao(7, fracao=1, plano=71, plano_nome="cFSC_ANTIGO",
                    hora="09:15")]
        return sessoes

    def test_o_numero_grande_nao_passa_do_total(self):
        """Era este o estrago: "16 / 15" com a barra cheia numa paciente que
        ainda tinha metade do tratamento pela frente."""
        t = self._quadro(self._mama_com_fsc())
        self.assertEqual(t.entregues, 8)
        self.assertLessEqual(t.entregues, t.previstas)

    def test_o_plano_de_agora_conta_as_frações_dele(self):
        t = self._quadro(self._mama_com_fsc())
        self.assertEqual(t.plano_entregues, 7)
        self.assertEqual(t.plano_previstas, 15)
        self.assertEqual(t.antes_do_plano_atual(), 1)

    def test_os_dois_planos_de_agora_aparecem_no_destaque(self):
        t = self._quadro(self._mama_com_fsc())
        self.assertEqual(t.plano_nome, "cMAMA_BOOSTD2 + cFSC_D2")
        self.assertTrue(t.simultaneos())
        self.assertEqual(t.juntos, 2)

    def test_o_par_de_agora_e_o_anterior_sao_DOIS_grupos(self):
        t = self._quadro(self._mama_com_fsc())
        self.assertEqual(t.planos, 2)
        self.assertTrue(t.replanejado())
        self.assertEqual(t.planos_distintos(), 4)

    def test_mama_com_FSC_sem_replanejamento_nao_e_replanejada(self):
        """Contando PLANOS em vez de grupos, toda paciente de mama com fossa
        saía "replanejada" — dois planos que nunca se substituíram. Aviso que
        acusa o que não houve some da vista quando houver de verdade."""
        sessoes = []
        for i, dia in enumerate([20, 19, 18]):
            fr = 3 - i
            sessoes += [
                _sessao(dia, fracao=fr, plano=72, plano_nome="cMAMA_D2",
                        hora="10:37", plano_previstas=15),
                _sessao(dia, fracao=fr, plano=73, plano_nome="cFSC_D2",
                        hora="10:42", plano_previstas=15)]
        t = self._quadro(sessoes)
        self.assertFalse(t.replanejado())
        self.assertEqual(t.entregues, 3)
        self.assertEqual(t.planos_distintos(), 2)

    def test_um_plano_com_o_total_zerado_nao_apaga_o_do_outro(self):
        """Basta um dos dois vir com ``FractionsPlanned`` nulo para a linha
        virar "3 de ?" num plano cujo total o banco sabe."""
        sessoes = [
            _sessao(20, fracao=3, plano=72, plano_nome="cMAMA_D2",
                    hora="10:37", plano_previstas=0),
            _sessao(20, fracao=3, plano=73, plano_nome="cFSC_D2",
                    hora="10:42", plano_previstas=15)]
        self.assertEqual(self._quadro(sessoes).plano_previstas, 15)


class TestQuadro(unittest.TestCase):
    """O que a tela calcula a partir das sessões."""

    def _tratamento(self, n: int, previstas: int = 25):
        # ``timedelta``, não ``dia - i``: com 30 sessões a subtração crua saía
        # do mês e o próprio teste explodia antes de testar coisa alguma.
        fim = date(2026, 8, 20)
        sessoes = [tratamento_db.Sessao(fracao=n - i, dose_cgy=200,
                                        data=fim - timedelta(days=i))
                   for i in range(n)]
        return tratamento_db.Tratamento(
            entregues=n, previstas=previstas,
            dose_entregue_cgy=200 * n, dose_prescrita_cgy=200 * previstas,
            sessoes=sessoes)

    def test_percentual(self):
        self.assertEqual(self._tratamento(12, 25).percentual(), 48)

    def test_sem_total_nao_inventa_percentual(self):
        """Sem o denominador do plano, 0% — e a tela diz que o total não veio.

        Um percentual calculado sobre um total desconhecido seria a barra de
        andamento afirmando um progresso que ninguém calculou.
        """
        self.assertEqual(self._tratamento(12, 0).percentual(), 0)

    def test_percentual_nao_passa_de_cem(self):
        """Retratamento e boost fazem entregues > previstas na mesma consulta."""
        self.assertEqual(self._tratamento(30, 25).percentual(), 100)

    def test_ultima_e_a_primeira_da_lista(self):
        """As sessões chegam da mais recente para trás (ORDER BY … DESC)."""
        t = self._tratamento(5)
        self.assertIs(t.ultima(), t.sessoes[0])
        self.assertEqual(t.ultima().fracao, 5)


class TestDoseDaPrescricao(unittest.TestCase):
    """O campo de dose é TEXTO, e tratá-lo como número fechou o app.

    Clicar num paciente no painel fazia a janela SUMIR — sem log, sem mensagem.
    ``sum(v.dose_cgy ...)`` levantava ``TypeError``, e exceção que escapa de um
    slot faz o PyQt5 chamar ``abort()``. Só acontecia com banco de verdade, que
    é por que nenhum teste de tela pegou.
    """

    def setUp(self):
        from isocentro.interface import controle_virtual
        self.cv = controle_virtual

    def test_texto_de_dose_vira_numero(self):
        self.assertEqual(self.cv.para_numero("4005"), 4005.0)
        self.assertEqual(self.cv.para_numero("40,05"), 40.05)

    def test_lixo_e_vazio_viram_zero_sem_explodir(self):
        """O DW tem "NA" e campo em branco; nenhum dos dois pode derrubar a tela."""
        for entrada in ("", None, "NA", "40 Gy", [], {}):
            self.assertEqual(self.cv.para_numero(entrada), 0.0)

    @staticmethod
    def _rx(*doses):
        from isocentro.banco import capa_dados
        return capa_dados.Prescricao(
            volumes=[capa_dados.Volume(nome=f"PTV{i}", dose_cgy=d)
                     for i, d in enumerate(doses)])

    def test_prescricao_com_dois_alvos_nao_soma(self):
        """Dois alvos de 5000 e 6000 cGy não são um tratamento de 11000.

        Num SIB são o mesmo tratamento com dose diferente por alvo; somar
        inventaria um total que ninguém prescreveu — e este número vai para o
        denominador da dose na tela.

        Chama ``dose_prescrita``, a função de PRODUÇÃO. A primeira versão deste
        teste reimplementava o ``max`` aqui dentro: voltar o código a ``sum``
        deixaria a suíte verde com o defeito de volta, que é o oposto de testar.
        """
        self.assertEqual(self.cv.dose_prescrita(self._rx("5000", "6000")),
                         6000.0)

    def test_prescricao_sem_volumes_nao_explode(self):
        """Prescrição aprovada sem anatomia existe no DW — e não pode derrubar."""
        self.assertEqual(self.cv.dose_prescrita(self._rx()), 0.0)
        self.assertEqual(self.cv.dose_prescrita(object()), 0.0)

    def test_prescricao_com_dose_ilegivel_vira_zero(self):
        self.assertEqual(self.cv.dose_prescrita(self._rx("NA", "")), 0.0)


class TestRedeDeSeguranca(unittest.TestCase):
    """Exceção não tratada tem de deixar RASTRO, não fechar a janela."""

    def test_excepthook_registra_e_nao_mata(self):
        from isocentro.interface import arranque
        original = sys.excepthook
        # A caixa é MODAL: deixá-la aparecer aqui trava a suíte esperando um
        # clique que nunca vem (aconteceu). O que se testa é o registro.
        caixa = arranque._avisar_erro
        vistos = []
        arranque._avisar_erro = vistos.append
        try:
            arranque._instalar_rede_de_seguranca()
            self.assertIsNot(sys.excepthook, original)
            # O logger é ``__name__``, e desde o pacote isso é o nome
            # COMPLETO. Deixar "gui" aqui faria o assertLogs escutar um logger
            # que ninguém mais usa — e o teste passaria a não provar nada.
            with self.assertLogs("isocentro.interface.arranque",
                                 level="CRITICAL") as capturado:
                try:
                    raise ValueError("defeito de exemplo")
                except ValueError:
                    sys.excepthook(*sys.exc_info())
            self.assertIn("defeito de exemplo", "\n".join(capturado.output))
            self.assertIn("Traceback", "\n".join(capturado.output))
            self.assertTrue(vistos, "a pessoa na frente da tela não foi avisada")
        finally:
            arranque._avisar_erro = caixa
            sys.excepthook = original

    def test_a_caixa_de_erro_nao_reentra(self):
        """Erro vindo de ``paintEvent`` abriria uma caixa POR REPINTURA.

        O ``exec`` da caixa modal roda o laço de eventos, então a repintura
        seguinte chamaria ``_avisar_erro`` de novo, por cima. O app ficaria
        impossível de fechar — pior que o ``abort()`` que esta rede substituiu:
        ao menos aquele terminava.
        """
        from isocentro.interface import arranque
        chamadas = []
        # Espia ``ui.falhar``, o caminho de erro desde o padrão de pop-ups de
        # 25/08/2026. GUARDA E DEVOLVE: ``del arranque.ui.falhar`` apagaria a função
        # ORIGINAL do módulo para o resto do processo.
        original = arranque.ui.falhar

        def falsa(*_a, **_k):
            chamadas.append(1)
            arranque._avisar_erro("de dentro da própria caixa")   # a reentrada
            return None

        arranque.ui.falhar = falsa
        try:
            arranque._avisar_erro("primeiro erro")
        finally:
            arranque.ui.falhar = original
            arranque._avisando = False
        self.assertEqual(len(chamadas), 1, "a caixa reentrou")

    def test_ctrl_c_continua_encerrando(self):
        """Transformar Ctrl+C em caixa de diálogo tornaria o app infechável
        pelo console."""
        from isocentro.interface import arranque
        original = sys.excepthook
        chamou = []
        try:
            arranque._instalar_rede_de_seguranca()
            padrao = sys.__excepthook__
            sys.__excepthook__ = lambda *a: chamou.append(a)
            try:
                sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            finally:
                sys.__excepthook__ = padrao
            self.assertTrue(chamou)
        finally:
            sys.excepthook = original


class TestMarcasDoPainel(unittest.TestCase):
    """As marcas de atenção — a "revisão semanal" feita pelo app.

    Nenhuma delas o médico enxerga hoje sem abrir paciente por paciente; é o
    que justifica a aba ser aberta de manhã em vez de quando alguém lembra.
    """

    HOJE = date(2026, 8, 19)

    @staticmethod
    def _linha(**kw):
        base = dict(nome="X", entregues=8, previstas=30, ultima=date(2026, 8, 19))
        base.update(kw)
        return tratamento_db.EmTratamento(**base)

    def _simbolos(self, **kw):
        return [s for s, _t in self._linha(**kw).marcas(self.HOJE)]

    def test_parada_conta_dias_uteis(self):
        """Sexta → quarta são 5 de calendário e 2 úteis: ainda não é parada.

        Contando corrido, todo fim de semana viraria alarme, e alarme que
        aparece sempre deixa de ser lido.
        """
        self.assertNotIn("⚠", self._simbolos(ultima=date(2026, 8, 14)))
        self.assertIn("⚠", self._simbolos(ultima=date(2026, 8, 12)))

    def test_curso_terminado_nao_esta_parado(self):
        """Está PRONTO, não parado. Marcar quem acabou encheria a lista."""
        self.assertNotIn("⚠", self._simbolos(entregues=30, previstas=30,
                                             ultima=date(2026, 7, 1)))

    def test_interrupcao_nao_e_marca(self):
        """Decidido pelo usuário em 11/09/2026: "se o tratamento foi realizado
        é o que interessa".

        O ⚡ de "última sessão interrompida" caía em quem não teve interrupção
        nenhuma — numa paciente de 2/15 que a sala confirmou normal, e em
        quatro pacientes em quase TODA sessão. O ``TerminationStatus`` do DW
        não é o que a sala viu, e marca que aparece sempre é ruído que faz
        parar de ler as outras.
        """
        self.assertNotIn("TerminationStatus", tratamento_db._SQL_EM_TRATAMENTO)
        self.assertFalse(hasattr(self._linha(), "interrompidas"))

    def test_comecou_e_termina(self):
        self.assertIn("●", self._simbolos(entregues=1))
        self.assertIn("✓", self._simbolos(entregues=29, previstas=30))
        self.assertIn("✓", self._simbolos(entregues=30, previstas=30))

    def test_troca_de_maquina(self):
        self.assertIn("⇄", self._simbolos(maquinas=2))
        self.assertNotIn("⇄", self._simbolos(maquinas=1))

    def test_sem_previstas_nao_afirma_conclusao(self):
        """Sem denominador não dá para dizer que concluiu — e "concluído" é o
        que faz o médico parar de olhar."""
        linha = self._linha(entregues=10, previstas=0)
        self.assertFalse(linha.concluido())
        self.assertNotIn("✓", [s for s, _t in linha.marcas(self.HOJE)])

    def test_urgencia_poe_o_parado_na_frente(self):
        """Por data, quem parou cai no FIM — parou de tratar, parou de aparecer.

        É o oposto do que a lista serve: ordenada por data ela mostra primeiro
        quem está indo bem.
        """
        parado = self._linha(ultima=date(2026, 8, 5))
        tratando = self._linha(ultima=date(2026, 8, 19))
        self.assertGreater(parado.urgencia(self.HOJE),
                           tratando.urgencia(self.HOJE))

    def test_parada_mais_longa_vem_antes(self):
        duas_semanas = self._linha(ultima=date(2026, 8, 3))
        tres_dias = self._linha(ultima=date(2026, 8, 13))
        self.assertGreater(duas_semanas.urgencia(self.HOJE),
                           tres_dias.urgencia(self.HOJE))

    def test_concluido_vai_para_o_fim(self):
        """Quando o filtro os inclui, eles não podem empurrar quem trata."""
        concluido = self._linha(entregues=30, previstas=30)
        comum = self._linha()
        self.assertLess(concluido.urgencia(self.HOJE), comum.urgencia(self.HOJE))

    def test_a_lista_nasce_fechada(self):
        """As consultas do painel agregam 2,7 milhões de linhas e cruzam com
        DimPatientDoctor. Nenhuma foi medida — nem o resultado, nem o tempo."""
        self.assertEqual(tratamento_db.LISTA_VERIFICADA_EM, "")
        self.assertFalse(tratamento_db.lista_disponivel())
        self.assertIsNone(tratamento_db.em_tratamento())
        self.assertEqual(tratamento_db.medicos(), [])

    def test_dias_alternados_nao_acaba_na_sexta(self):
        """Devolvido pelo usuário em 21/08/2026 (uma SEXTA), sobre o Tadeu
        Amostro: 1/3 em dias alternados, "ele não acaba essa semana né, sábado e
        domingo não funciona".

        A próxima cai na segunda e a última na quarta — contar só "faltam 2"
        punha o paciente na faixa de quem termina em três dias.
        """
        sexta = date(2026, 8, 21)
        tadeu = self._linha(entregues=1, previstas=3, ultima=date(2026, 8, 20),
                            frequencia="Dias Alternados")
        self.assertEqual(tadeu.previsao_de_fim(sexta), date(2026, 8, 26))
        self.assertEqual(tratamento_db.faixa(tadeu, sexta),
                         tratamento_db.FAIXA_CURSO)

    def test_a_faixa_conta_o_CALENDARIO_e_nao_as_fracoes(self):
        """A faixa saiu com sete pacientes numa sexta — entre eles um de 21/25
        e dois de 2/5, que não terminam semana nenhuma."""
        sexta = date(2026, 8, 21)
        nair = self._linha(entregues=21, previstas=25, ultima=sexta,
                           frequencia="Uma Vez por Dia")
        self.assertEqual(nair.previsao_de_fim(sexta), date(2026, 8, 27))
        self.assertEqual(tratamento_db.faixa(nair, sexta),
                         tratamento_db.FAIXA_CURSO)

    def test_quem_termina_de_fato_nesta_semana_fica_na_faixa(self):
        """A correção não pode esvaziar a faixa: numa segunda, quem tem duas
        frações diárias pela frente termina na quarta."""
        segunda = date(2026, 8, 24)
        linha = self._linha(entregues=13, previstas=15, ultima=segunda,
                            frequencia="Uma Vez por Dia")
        self.assertEqual(linha.previsao_de_fim(segunda), date(2026, 8, 26))
        self.assertEqual(tratamento_db.faixa(linha, segunda),
                         tratamento_db.FAIXA_TERMINA)

    def test_a_previsao_pula_o_fim_de_semana(self):
        """Sábado e domingo não tratam — somar dias corridos poria o fim dois
        dias antes do que ele é."""
        self.assertEqual(
            tratamento_db._somar_dias_uteis(date(2026, 8, 21), 1),
            date(2026, 8, 24))
        self.assertEqual(tratamento_db.sexta_desta_semana(date(2026, 8, 19)),
                         date(2026, 8, 21))
        # Sábado pertence, para quem lê a lista, à semana de trabalho seguinte.
        self.assertEqual(tratamento_db.sexta_desta_semana(date(2026, 8, 22)),
                         date(2026, 8, 28))

    def test_paciente_parado_nao_vira_quem_termina(self):
        """Partindo da última sessão de duas semanas atrás, a previsão cairia
        no PASSADO e todo parado entraria na faixa de quem termina."""
        sexta = date(2026, 8, 21)
        parado = self._linha(entregues=5, previstas=6,
                             ultima=date(2026, 8, 5),
                             frequencia="Uma Vez por Dia")
        # Nunca no passado — o piso é hoje.
        self.assertGreaterEqual(parado.previsao_de_fim(sexta), sexta)
        self.assertEqual(tratamento_db.faixa(parado, sexta),
                         tratamento_db.FAIXA_ATENCAO)

    def test_as_faixas_separam_o_que_exige_decisao_hoje(self):
        """Pedido do usuário em 21/08/2026 olhando o painel.

        A ordenação por urgência já punha as linhas certas em cima, mas ordem
        sozinha não diz onde um assunto termina e o outro começa — quem varre a
        lista de manhã quer saber QUANTOS casos exigem decisão hoje, e isso é
        contagem, não posição.
        """
        parado = self._linha(ultima=date(2026, 8, 5))
        # 28 de 30 numa quarta: as duas que faltam cabem em quinta e sexta.
        termina = self._linha(entregues=28, previstas=30)
        andando = self._linha(entregues=8, previstas=30)
        faixas = tratamento_db.por_faixa(
            [parado, termina, andando], self.HOJE)
        self.assertEqual([c for c, _t, _l in faixas],
                         [tratamento_db.FAIXA_ATENCAO,
                          tratamento_db.FAIXA_TERMINA,
                          tratamento_db.FAIXA_CURSO])
        self.assertEqual([len(l) for _c, _t, l in faixas], [1, 1, 1])

    def test_faixa_vazia_nao_vira_titulo(self):
        """Título sobre nada é espaço reservado por via das dúvidas — e ainda
        promete uma seção que não existe naquele dia."""
        faixas = tratamento_db.por_faixa([self._linha()], self.HOJE)
        self.assertEqual([c for c, _t, _l in faixas],
                         [tratamento_db.FAIXA_CURSO])

    def test_concluido_nao_entra_em_atencao(self):
        """Quem terminou não está parado: pô-lo em atenção encheria justamente
        a faixa que existe para ser curta."""
        pronto = self._linha(entregues=30, previstas=30,
                             ultima=date(2026, 7, 1))
        self.assertEqual(tratamento_db.faixa(pronto, self.HOJE),
                         tratamento_db.FAIXA_CONCLUIDO)

    def test_toda_linha_cai_em_alguma_faixa(self):
        """Linha sem faixa SOME da tela — o pior desfecho possível numa lista
        de pacientes."""
        casos = [self._linha(), self._linha(entregues=1),
                 self._linha(entregues=30, previstas=30),
                 self._linha(previstas=0), self._linha(ultima=None)]
        faixas = tratamento_db.por_faixa(casos, self.HOJE)
        self.assertEqual(sum(len(l) for _c, _t, l in faixas), len(casos))

    def _lista_falseada(self, linha, fracoes, frequencias=(), **kw):
        """Roda ``em_tratamento`` com o banco respondendo o que se mandar.

        ``linha``: a linha da consulta principal (a do ``FractionsDelivered``).
        Dez colunas desde 24/09/2026 — ``inicio`` (a PRIMEIRA sessão do
        curso, ``MIN(TreatmentStartTime)``) entrou entre ``previstas`` e
        ``ultima``; as duas últimas continuam o médico do paciente e quantos
        oncologistas ele tem vinculados (o Grupo Médico).
        ``fracoes``: as linhas da recontagem — ``(registro, curso, plano, dia)``,
        uma por (plano, fração), que é o mesmo grão do quadro do paciente.
        """
        disponivel = tratamento_db.lista_disponivel
        consultar = capa_db_modulo._consultar
        tratamento_db.lista_disponivel = lambda: True

        def responder(sql, *_a, **_k):
            # Cada auxiliar é reconhecida pelo que só ela tem. "IN (" sozinho
            # não serve: a consulta PRINCIPAL já teve um ``IN (...)`` no
            # status de término (o ⚡, que saiu em 11/09/2026), e com o
            # casamento largo ela era respondida como se fosse auxiliar — a
            # lista voltava vazia e os testes acusavam defeito que não existia.
            if "DimPrescriptionProperty" in sql:
                return frequencias                 # a frequência prescrita
            if "COUNT(DISTINCT th.DimCourseID)" in sql:
                return []                          # a contagem de cursos
            if "PatientId IN (" in sql:
                return fracoes                     # a recontagem de frações
            return [linha]

        capa_db_modulo._consultar = responder
        try:
            return tratamento_db.em_tratamento(**kw)
        finally:
            capa_db_modulo._consultar = consultar
            tratamento_db.lista_disponivel = disponivel

    def test_replanejamento_nao_deixa_a_lista_atras_do_quadro(self):
        """Visto na tela em 21/08/2026, paciente 9000012CEL.

        A lista dizia "13/15 · faltam 2 · parado há 14 dias úteis" e o quadro,
        na MESMA tela, dizia "15 / 15 — tratamento concluído". Ela terminou em
        31/07: são três planos (13 frações, 1 e 1), a numeração de fração
        reinicia a cada replanejamento, e o ``MAX(FractionsDelivered)`` da
        lista só enxergava o maior deles.

        Mandar procurar quem já acabou custa a atenção de quem parou de verdade.
        """
        fracoes = [("9000012CEL", 7, 101, f"202607{d:02d}") for d in range(8, 21)]
        fracoes += [("9000012CEL", 7, 102, "20260730"),
                    ("9000012CEL", 7, 103, "20260731")]
        linha = ("9000012CEL", "Beltrana, Marlene de Almeida", 7, 13, 15,
                 None, None, 2, "Saldanha, Thais", 1)
        lista = self._lista_falseada(linha, fracoes, incluir_concluidos=True)
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0].entregues, 15)
        self.assertEqual(lista[0].faltam(), 0)
        self.assertTrue(lista[0].concluido())

    def test_quem_terminou_sai_da_lista_de_quem_esta_em_tratamento(self):
        """O ``HAVING`` do SQL corta pelo número do DW, que estava atrasado —
        quem a recontagem descobre concluído tem de sair aqui."""
        fracoes = [("9000012CEL", 7, 101, f"202607{d:02d}") for d in range(8, 21)]
        fracoes += [("9000012CEL", 7, 102, "20260730"),
                    ("9000012CEL", 7, 103, "20260731")]
        linha = ("9000012CEL", "Beltrana, Marlene de Almeida", 7, 13, 15,
                 None, None, 2, "Saldanha, Thais", 1)
        self.assertEqual(self._lista_falseada(linha, fracoes), [])

    def test_planos_simultaneos_nao_dobram_a_lista(self):
        """A correção óbvia — somar ``FractionsDelivered`` por plano — erraria
        pelo outro lado: mama e FSC tratam JUNTAS, e 7 + 7 daria 14 sessões
        onde houve 7. É o defeito que o quadro já levou em 20/08."""
        fracoes = [("9000013CEL", 9, plano, f"202608{d:02d}")
                   for d in range(12, 19) for plano in (201, 202)]
        linha = ("9000013CEL", "Fulana, Mama", 9, 7, 15, None, None, 1,
                 "Saldanha, Thais", 1)
        lista = self._lista_falseada(linha, fracoes, incluir_concluidos=True)
        self.assertEqual(lista[0].entregues, 7)

    def test_a_frequencia_do_banco_chega_traduzida(self):
        """De ponta a ponta: o "dias alternado" do banco (em inglês de fábrica
        ou digitado pela equipe) tem de virar "Dias Alternados" traduzido — é
        o ritmo que dá a data do fim. O caso era o do Tadeu Amostro."""
        quando = datetime(2026, 8, 20, 14, 30)
        linha = ("9X", "Amostro, Tadeu", 4, 1, 3, None, quando, 1,
                 "Saldanha, Thais", 1)
        lista = self._lista_falseada(
            linha, [("9X", 4, 501, "20260820")],
            frequencias=[("9X", 4, "dias alternado")])
        self.assertEqual(lista[0].frequencia, "Dias Alternados")

    def test_duas_prescricoes_no_mesmo_curso_nao_sorteiam_a_frequencia(self):
        """Mama diária + boost em dias alternados é o caso do serviço.

        O dict ficava com a ÚLTIMA linha que o banco mandasse, e a consulta não
        tinha ``ORDER BY``: a mesma paciente pulava de faixa entre dois
        refreshes, sem nada ter mudado no tratamento. Ganha a DIÁRIA — quem tem
        um plano diário deita na mesa todo dia útil.
        """
        quando = datetime(2026, 8, 20, 14, 30)
        linha = ("7X", "Fulana, Mama", 4, 1, 3, None, quando, 1,
                 "Saldanha, Thais", 1)
        for ordem in ([("7X", 4, "once daily"), ("7X", 4, "dias alternado")],
                      [("7X", 4, "dias alternado"), ("7X", 4, "once daily")]):
            lista = self._lista_falseada(
                linha, [("7X", 4, 501, "20260820")], frequencias=ordem)
            self.assertEqual(lista[0].frequencia, "Uma Vez por Dia",
                             f"ordem do banco mudou a resposta: {ordem}")

    def test_curso_so_com_regimes_alternados_escolhe_sempre_o_mesmo(self):
        """Sem nenhuma diária a escolha é arbitrária — mas tem de ser ESTÁVEL,
        que é o que faltava."""
        quando = datetime(2026, 8, 20, 14, 30)
        linha = ("8X", "Fulano, Alternado", 4, 1, 3, None, quando, 1,
                 "Saldanha, Thais", 1)
        vistos = set()
        for ordem in ([("8X", 4, "twice weekly"), ("8X", 4, "dias alternado")],
                      [("8X", 4, "dias alternado"), ("8X", 4, "twice weekly")]):
            lista = self._lista_falseada(
                linha, [("8X", 4, 501, "20260820")], frequencias=ordem)
            vistos.add(lista[0].frequencia)
        self.assertEqual(len(vistos), 1, f"a ordem do banco decidiu: {vistos}")

    def test_recontagem_que_falha_deixa_o_numero_do_banco(self):
        """Sem ela a lista é a que sempre foi — e o painel já anuncia, em faixa,
        que não está conferido. Tela nenhuma seria pior que número discutível."""
        disponivel = tratamento_db.lista_disponivel
        consultar = capa_db_modulo._consultar
        tratamento_db.lista_disponivel = lambda: True

        def responder(sql, *_a, **_k):
            # "PatientId IN (" cobre as três auxiliares (``p.`` e ``pac.``).
            if "PatientId IN (" in sql:
                raise capa_db_modulo.FalhaDeLeitura("derrubada")
            return [("1X", "Fulano", 3, 12, 25, None, None, 1,
                    "Saldanha, Thais", 1)]

        capa_db_modulo._consultar = responder
        try:
            lista = tratamento_db.em_tratamento()
        finally:
            capa_db_modulo._consultar = consultar
            tratamento_db.lista_disponivel = disponivel
        self.assertEqual(lista[0].entregues, 12)

    def test_falha_de_leitura_nao_vira_lista_vazia(self):
        """"Não consegui perguntar" e "não há ninguém" são respostas OPOSTAS.

        Devolvendo as duas como `[]`, a aba afirmou "ninguém em tratamento
        nesta janela" para um médico com agenda cheia — e o motivo real era uma
        consulta que nem chegou a rodar.
        """
        original = tratamento_db.lista_disponivel
        tratamento_db.lista_disponivel = lambda: True
        consultar = capa_db_modulo._consultar

        def explodir(*_a, **_k):
            raise capa_db_modulo.FalhaDeLeitura("derrubada")

        capa_db_modulo._consultar = explodir
        try:
            self.assertIsNone(tratamento_db.em_tratamento())
        finally:
            capa_db_modulo._consultar = consultar
            tratamento_db.lista_disponivel = original


@unittest.skipIf(tratamento is None, "PySide6 indisponível")
class TestTelaSemBanco(unittest.TestCase):
    """Sem banco apontado — o estado de qualquer estação recém-instalada.

    Era "portão fechado" até 19/08/2026; com o portão aberto, o caminho que
    sobra para a tela vazia é este, e ele continua importando: instalação nova
    abre sem o campo "Sistema" preenchido, e a aba tem de dizer isso em vez de
    mostrar um zero que parece dado.
    """

    def setUp(self):
        """Isola de QUALQUER banco apontado nesta máquina.

        O teste presumia "sem `config_servico.json` no repositório" e passou a
        falhar assim que o app foi aberto uma vez na pasta do projeto: ele
        gravou um `config_servico.json` apontando o SRVINSIGHT, e a partir daí
        `configurado()` era `True`. Apontar `ISOCENTRO_CONFIG` para uma pasta
        vazia torna o teste independente do que existe na estação.
        """
        import tempfile
        self._env = {k: os.environ.get(k)
                     for k in ("ISOCENTRO_CONFIG", "ISOCENTRO_DB_SERVIDOR",
                               "ISOCENTRO_DB_SERVIDOR")}
        os.environ["ISOCENTRO_CONFIG"] = tempfile.mkdtemp(prefix="cfg_vazia_")
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        # Os DOIS nomes: desde 09/09/2026 o ``capa_db`` lê pelo ``ambiente.ler``
        # e o ``ISOCENTRO_DB_SERVIDOR`` tem PRECEDÊNCIA — tirar só o antigo
        # deixaria o banco apontado numa estação que já migrou, e o teste
        # falharia só nela.
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)

    def tearDown(self):
        for chave, antigo in self._env.items():
            if antigo is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = antigo

    def test_abre_sem_numero_e_o_motivo_toma_a_tela(self):
        """Tela vazia com o motivo escrito, nunca um zero que parece dado.

        E o motivo toma a tela: a primeira versão o pôs numa linha de rodapé,
        com cabeçalho e busca vazios esticados acima — a tela parecia quebrada,
        e o único texto que explicava o que houve era o menor da janela.
        """
        p = tratamento.PainelFichaVirtual()
        p.show()
        try:
            self.assertFalse(p._cartao_quadro.isVisible())
            self.assertFalse(p.cartao_busca.isVisible())
            self.assertTrue(p._cartao_aviso.isVisible())
            self.assertTrue(p.aviso_texto.text())
        finally:
            _destruir(p)


@unittest.skipIf(tratamento is None, "PySide6 indisponível")
class TestTela(unittest.TestCase):
    """A tela com o portão ABERTO — como ela ficará conferido o mapeamento.

    O portão é aberto aqui de propósito: sem isso estes testes só provariam que
    a tela sabe se esconder, e a metade que importa (os números grandes, a
    busca que sai da frente) nunca seria exercitada.
    """

    def setUp(self):
        self._verificado = tratamento_db.VERIFICADO_EM
        tratamento_db.VERIFICADO_EM = "01/01/2026"
        # ``disponivel()`` exige as DUAS coisas: mapeamento conferido e banco
        # apontado. Sem o servidor aqui, a tela continuaria no aviso e estes
        # testes provariam só que ela sabe se esconder. Nada é consultado — a
        # tela recebe o tratamento pronto de quem monta a janela.
        self._servidor = os.environ.get("ISOCENTRO_DB_SERVIDOR")
        # Tirar o nome NOVO antes de gravar o antigo: ele tem precedência no
        # ``ambiente.ler`` e venceria o ``SERVIDOR_DE_TESTE`` daqui.
        self._servidor_novo = os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        os.environ["ISOCENTRO_DB_SERVIDOR"] = "SERVIDOR_DE_TESTE"
        self.p = tratamento.PainelFichaVirtual()
        self.p.show()      # sem isto, ``isVisible`` é False em tudo

    def tearDown(self):
        _destruir(self.p)
        tratamento_db.VERIFICADO_EM = self._verificado
        for nome, valor in (("ISOCENTRO_DB_SERVIDOR", self._servidor),
                            ("ISOCENTRO_DB_SERVIDOR", self._servidor_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    def test_escolhido_o_paciente_a_busca_sai_da_frente(self):
        """Ela é o bloco mais alto da tela e empurra para baixo o que se veio ver.

        No lugar dela fica o botão de trocar, no canto do cabeçalho — perto da
        identidade, que é o que ele troca.
        """
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=3, previstas=5, sessoes=[_sessao(19, fracao=3)]))
        self.assertFalse(self.p.cartao_busca.isVisible())
        self.assertTrue(self.p.btn_trocar.isVisible())
        self.p._trocar_paciente()
        self.assertTrue(self.p.cartao_busca.isVisible())
        self.assertFalse(self.p.btn_trocar.isVisible())

    def test_none_nao_vira_zero_de_zero(self):
        """"Não deu para saber" e "não tratou ainda" são coisas diferentes.

        Mostrando 0/0 para uma falha de leitura, o médico concluiria que o
        paciente não começou o tratamento — que é o oposto do que se sabe.
        """
        self.p.mostrar(None)
        self.assertFalse(self.p._cartao_quadro.isVisible())
        self.assertTrue(self.p.status.text())

    def test_fracao_grande_e_o_total_separado(self):
        t = tratamento_db.Tratamento(entregues=12, previstas=25,
                                     sessoes=[_sessao(19, fracao=12)])
        self.p.mostrar(t)
        self.assertEqual(self.p.fracao.valor.text(), "12")
        self.assertIn("25", self.p.fracao.total.text())
        self.assertIn("48%", self.p.pct.text())

    def test_sem_quem_tratou_a_tela_diz_que_nao_sabe(self):
        """O campo pode simplesmente não existir no data warehouse.

        Regra do projeto: campo sem fonte nasce vazio e a tela avisa. Aqui isso
        pesa mais que em qualquer outra tela — atribuir a sessão a quem não a
        fez é pior do que não dizer quem fez.
        """
        t = tratamento_db.Tratamento(entregues=1, previstas=5,
                                     sessoes=[_sessao(19, fracao=1)])
        self.p.mostrar(t)
        self.assertIn("não informado", self.p.tabela.item(0).text())

    def test_lista_traz_uma_linha_por_sessao(self):
        t = tratamento_db.Tratamento(
            entregues=3, previstas=5,
            sessoes=[_sessao(19, fracao=3, quem="J. Silva", maquina="TB1"),
                     _sessao(18, fracao=2, quem="J. Silva", maquina="TB1"),
                     _sessao(17, fracao=1, quem="A. Costa", maquina="TB2")])
        self.p.mostrar(t)
        self.assertEqual(self.p.tabela.count(), 3)
        self.assertIn("J. Silva", self.p.tabela.item(0).text())

    def _com_dois_planos(self, **campos):
        """Um dia de mama + FSC: duas linhas com a MESMA fração."""
        sessoes = [
            _sessao(20, fracao=3, plano=72, plano_nome="cMAMA_D2", hora="10:37"),
            _sessao(20, fracao=3, plano=73, plano_nome="cFSC_D2", hora="10:42")]
        dados = dict(entregues=3, previstas=15, juntos=2, planos=1,
                     plano_nome="cMAMA_D2 + cFSC_D2", plano_entregues=3,
                     plano_previstas=15, sessoes=sessoes)
        dados.update(campos)
        return tratamento_db.Tratamento(**dados)

    def test_a_tela_explica_por_que_ha_duas_linhas_da_fracao_3(self):
        """Sem esta frase, a lista parece ter contado a mesma sessão duas vezes
        e o número grande parece errado — foi essa a dúvida no uso real."""
        self.p.mostrar(self._com_dois_planos())
        self.assertIn("juntos", self.p.planos.text())
        self.assertTrue(self.p.planos.isVisible())

    def test_dois_planos_juntos_nao_sao_anunciados_como_replanejamento(self):
        self.p.mostrar(self._com_dois_planos())
        self.assertNotIn("replanejado", self.p.planos.text())

    def test_a_coluna_do_plano_aparece_sem_ter_havido_replanejamento(self):
        """Duas linhas de "fração 3" no mesmo dia, e nada dizendo que são de
        planos diferentes: a coluna vinha só no replanejamento."""
        self.p.mostrar(self._com_dois_planos())
        self.assertIn("cMAMA_D2", self.p.tabela.item(0).text())
        self.assertIn("cFSC_D2", self.p.tabela.item(1).text())

    def test_dois_planos_juntos_saem_no_PLURAL_no_destaque(self):
        self.p.mostrar(self._com_dois_planos())
        self.assertTrue(self.p.plano_rot.text().startswith("PLANOS"))

    def test_um_plano_so_continua_no_singular(self):
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=3, previstas=15, juntos=1, planos=1,
            plano_nome="cMAMA_D2", sessoes=[_sessao(20, fracao=3, plano=72)]))
        self.assertEqual(self.p.plano_rot.text(), "PLANO")

    def _chips_extra(self) -> list:
        linha = self.p.cabecalho.linha_extra
        return [linha.itemAt(i).widget().text()
                for i in range(linha.count())
                if hasattr(linha.itemAt(i).widget(), "text")]

    # PNG 1×1 de verdade: ``Retrato.definir`` carrega os bytes num ``QPixmap`` e
    # descarta o que não for imagem — com bytes inventados o teste passaria sem
    # nunca ter havido foto na tela.
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8"
        "BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    def test_a_foto_sobrevive_a_chegada_do_medico(self):
        """``CabecalhoPaciente.definir`` repõe TUDO da faixa. Repintá-la para
        acrescentar o médico apagava a 3×4 do paciente, que é o que confere de
        relance se a tela é de quem se pensa."""
        self.p.definir_foto(self.PNG)
        self.p.mostrar(tratamento_db.Tratamento(
            registro="9000001CEL", entregues=1, previstas=1,
            medico="Camila Sampaio", sessoes=[_sessao(19, fracao=1)]))
        self.assertTrue(self.p.cabecalho.retrato._tem)

    def test_a_foto_do_paciente_ANTERIOR_nao_sobrevive_a_troca(self):
        """Foto errada nesse posto mente com mais força que qualquer campo."""
        self.p.definir_foto(self.PNG)
        self.p.definir_pacientes([
            capa_dados_modulo.PacienteRef(registro="9X", nome="OUTRO PACIENTE")])
        self.p.busca.setText("outro")
        self.p.lista.setCurrentRow(0)
        self.p._escolher()
        self.assertFalse(self.p.cabecalho.retrato._tem)

    def test_medico_aparece_na_faixa_de_identidade(self):
        """"De quem é este paciente?" é pergunta da faixa de cima. E o
        tratamento sai da tabela da equipe: "Dr." fixo erraria com a maioria
        desta, e deduzir do primeiro nome tropeça em "Lais", "Jean", "Keiko"."""
        self.p._pintar_cabecalho("9000001CEL", "MARIA DE SOUZA",
                                 "Nicole Mayer Arruda Falcao")
        self.assertIn("Dra. Nicole Mayer Arruda Falcao", self._chips_extra())

    def test_medico_chega_com_o_quadro_e_nao_no_clique(self):
        """Buscá-lo no gesto de escolher travava a tela até o servidor
        responder — 8 s com o banco fora do ar, medido na suíte."""
        self.p._pintar_cabecalho("9000001CEL", "MARIA DE SOUZA")
        self.assertEqual(self._chips_extra(), [])
        self.p.mostrar(tratamento_db.Tratamento(
            registro="9000001CEL", entregues=1, previstas=1,
            medico="Fernando Batista Rezende",
            sessoes=[_sessao(19, fracao=1, quem="Michele Soares")]))
        self.assertIn("Dr. Fernando Batista Rezende", self._chips_extra())

    def test_sem_medico_a_pilula_nao_fica_em_branco(self):
        """Pílula vazia lê-se como dado faltando — e o banco não responde por
        todo paciente."""
        self.p._pintar_cabecalho("9000001CEL", "MARIA DE SOUZA", "")
        self.assertEqual(self._chips_extra(), [])

    def test_o_segundo_tecnico_aparece_ao_lado(self):
        """Na sala são duas pessoas posicionando o paciente
        (``TreatmentSignOffUser2``), e a folha nomeava uma só."""
        t = tratamento_db.Tratamento(
            entregues=1, previstas=1,
            sessoes=[_sessao(19, fracao=1, quem="Michele Soares",
                             ajudante="Jonas Souza Santos", maquina="6EX")])
        self.p.mostrar(t)
        linha = self.p.tabela.item(0).text()
        self.assertIn("Michele Soares · Jonas Souza Santos", linha)

    def test_segundo_tecnico_vazio_nao_deixa_sujeira(self):
        """A maioria das linhas vem sem ele — e o separador solto no fim da
        coluna parece dado faltando."""
        t = tratamento_db.Tratamento(
            entregues=1, previstas=1,
            sessoes=[_sessao(19, fracao=1, quem="Michele Soares", maquina="6EX")])
        self.p.mostrar(t)
        self.assertNotIn("·", self.p.tabela.item(0).text().split("6EX")[1])

    def test_o_mesmo_nome_nos_dois_campos_nao_se_repete(self):
        """A máquina copia o operador para o segundo campo quando não há
        ajudante, e o nome repetido lado a lado parece erro de tela."""
        s = _sessao(19, fracao=1, quem="Michele Soares",
                    ajudante="Michele Soares", maquina="6EX")
        self.assertEqual(s.quem_tratou(), "Michele Soares")

    def test_colunas_da_lista_nao_se_encostam(self):
        """Um nome de 14 caracteres na coluna que reservava 12: o nome de quem
        tratou colava na máquina, sem espaço nenhum ("...SN1002Elaine"). Foi o
        que o usuário viu na tela em 20/08/2026.

        Eram 14 porque a lista mostrava "TBuniverSN1002"; hoje ela mostra o
        nome do serviço (TrueBeam, 8), então quem carrega o caso longo aqui é
        um nome com prefixo de sala — que existe no acervo e é o que o
        ``rotulo_maquina`` preserva."""
        t = tratamento_db.Tratamento(
            entregues=2, previstas=2,
            sessoes=[_sessao(19, fracao=2, quem="Elaine Luiza dos Soares",
                             maquina="Sala2-TBuniverSN1002"),
                     _sessao(18, fracao=1, quem="Wagner Cesar de Sousa",
                             maquina="6EX")])
        self.p.mostrar(t)
        for i in range(self.p.tabela.count()):
            linha = self.p.tabela.item(i).text()
            for maquina in ("Sala2-TrueBeam", "6EX"):
                if maquina in linha:
                    depois = linha.split(maquina, 1)[1]
                    self.assertTrue(depois.startswith("   "), linha)

    def test_colunas_alinham_entre_linhas(self):
        """A largura é medida na lista INTEIRA. Medida por linha, "6EX" e
        "TBuniverSN1002" começariam o nome em colunas diferentes — e coluna
        quase alinhada é pior de ler que texto corrido."""
        t = tratamento_db.Tratamento(
            entregues=2, previstas=2,
            sessoes=[_sessao(19, fracao=2, quem="Elaine", maquina="TBuniverSN1002"),
                     _sessao(18, fracao=1, quem="Wagner", maquina="6EX")])
        self.p.mostrar(t)
        colunas = {self.p.tabela.item(i).text().index(nome)
                   for i, nome in enumerate(("Elaine", "Wagner"))}
        self.assertEqual(len(colunas), 1, "o nome começa em colunas diferentes")

    def test_cabecalho_das_colunas_para_em_cima_delas(self):
        """O rótulo é montado com as MESMAS larguras das linhas; com um número
        fixo, "MÁQUINA" flutuaria sobre a coluna do nome."""
        t = tratamento_db.Tratamento(
            entregues=1, previstas=1,
            sessoes=[_sessao(19, fracao=1, quem="Elaine Luiza dos Soares",
                             maquina="TBuniverSN1002")])
        self.p.mostrar(t)
        cab, linha = self.p.cab_colunas.text(), self.p.tabela.item(0).text()
        self.assertTrue(self.p.cab_colunas.isVisible())
        # A lista mostra o nome do serviço; o banco entrega o de fábrica.
        self.assertEqual(cab.index("MÁQUINA"), linha.index("TrueBeam"))
        self.assertEqual(cab.index("QUEM TRATOU"), linha.index("Elaine"))
        self.assertEqual(cab.index("DATA"), linha.index("19/08/2026"))

    @staticmethod
    def _pilulas(layout) -> list:
        """Os textos das pílulas de uma fileira do cabeçalho.

        Lidas do LAYOUT: ``CabecalhoPaciente`` monta as pílulas dentro dele e
        não guarda lista pública nenhuma — e pílula sem texto some da faixa.
        """
        fora = []
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w is not None and getattr(w, "text", None) and w.text():
                fora.append(w.text())
        return fora

    def test_a_faixa_traz_nascimento_convenio_e_MAQUINA(self):
        """Pedido em 21/08/2026: as mesmas pílulas da Capa, para quem alterna
        entre as duas abas do mesmo paciente não reaprender onde cada coisa
        está. A máquina é a da última sessão APLICADA — a que a pessoa está
        usando de fato, que muda quando há remanejamento."""
        t = tratamento_db.Tratamento(
            entregues=13, previstas=25, registro="9000020BET",
            medico="Rubens Augusto Leal Júnior",
            nascimento="14/03/1979", convenio="Unimed",
            sessoes=[_sessao(21, fracao=13, maquina="600CD")])
        self.p.mostrar(t)
        self.assertIn("14/03/1979", self._pilulas(self.p.cabecalho.linha_chips))
        self.assertIn("Unimed", self._pilulas(self.p.cabecalho.linha_chips))
        self.assertIn("600CD", self._pilulas(self.p.cabecalho.linha_extra))

    def test_sem_sessao_a_maquina_nao_inventa(self):
        """Paciente sem sessão aplicada não tem máquina ATUAL — e pílula em
        branco lê-se como dado faltando."""
        t = tratamento_db.Tratamento(entregues=0, previstas=25,
                                     nascimento="14/03/1979")
        self.p.mostrar(t)
        self.assertNotIn("600CD", self._pilulas(self.p.cabecalho.linha_extra))

    def test_a_lista_nao_oferece_mais_incluir_concluidos(self):
        """Tirado a pedido do usuário: o cartão chama-se EM TRATAMENTO, e a
        caixa oferecia um estado em que o título passava a mentir. Quem procura
        alguém que já teve alta chega pela BUSCA por nome."""
        self.assertFalse(self.p.incluir_concluidos())
        self.assertFalse(hasattr(self.p, "concluidos"))

    _PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
        "DwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

    def test_cortes_e_dvh_aparecem_com_a_PROCEDENCIA(self):
        """Pedido em 21/08/2026, para o espaço vazio ao lado das sessões.

        As imagens são as da FICHA JÁ ELABORADA — esta aba não tem DICOM para
        recalcular nada. Por isso o rodapé diz de que ficha elas vieram: um
        replanejamento gera ficha nova, e o corte de duas versões atrás mostra
        um alvo que já não é o do tratamento em curso.
        """
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_imagens(self._PNG, self._PNG,
                               "Da ficha elaborada em 20/08/2026 · versão 2")
        self.assertTrue(self.p._cartao_imagens.isVisible())
        self.assertTrue(self.p.img_cortes.tem_imagem())
        self.assertTrue(self.p.img_dvh.tem_imagem())
        self.assertIn("20/08/2026", self.p._procedencia_imagens)

    def test_o_cartao_de_fotos_segue_o_padrao_dos_cortes(self):
        """Pedido em 21/08/2026: "mesmas propriedades e padrão". Os dois são a
        mesma coisa para quem lê — duas imagens com o rodapé dizendo de onde
        vieram —, e cartões quase iguais leem-se pior que cartões iguais."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("PELVE - VAC LOCK",
                               [self._PNG, self._PNG], "")])
        self.assertTrue(self.p._cartao_fotos.isVisible())
        self.assertEqual(self.p._cartao_fotos.width(),
                         self.p._cartao_imagens.width())
        self.assertTrue(self.p.foto_a.tem_imagem())
        self.assertTrue(self.p.foto_b.tem_imagem())

    def test_sem_cadastro_de_simulacao_o_cartao_de_fotos_some(self):
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos()
        self.assertFalse(self.p._cartao_fotos.isVisible())

    def test_a_terceira_foto_e_anunciada_e_nao_escondida(self):
        """Duas é o que cabe; quem tem quatro precisa saber que há mais, senão
        conclui que viu a montagem inteira."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("MAMA", [self._PNG] * 4, "")])
        self.assertIn("+2", self.p._procedencia_fotos)

    def test_seletor_aparece_com_MAIS_DE_UM_posicionamento(self):
        """Crânio e metástase na mesma simulação são montagens diferentes, com
        notas diferentes. Achatadas numa lista só, as duas primeiras fotos
        saíam como se fossem da mesma."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("META", [self._PNG], "vac lock"),
                              ("CRÂNIO", [self._PNG], "máscara")])
        self.assertTrue(self.p.combo_setup.isVisible())
        self.assertEqual(self.p.combo_setup.count(), 2)
        self.assertIn("vac lock", self.p.nota._texto)
        self.p._trocar_setup(1)
        self.assertIn("máscara", self.p.nota._texto)
        self.assertIn("CRÂNIO", self.p.combo_setup.currentText())

    def test_a_nota_abre_pela_PALAVRA_do_titulo(self):
        """Escolhido com o usuário em 21/08/2026: a nota não ocupa lugar na
        tela. Como ladrilho ela roubava um terço da faixa das fotos para
        mostrar texto ilegível de tão miúdo; a palavra do título é a porta."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("TORAX", [self._PNG],
                               "VAC LOCK\n\nBEXIGA: CHEIA")])
        self.assertTrue(self.p.nota.tem_nota())
        self.assertEqual(self.p.nota.text(), "POSICIONAMENTO")
        self.assertEqual(self.p.nota.cursor().shape(), Qt.PointingHandCursor)
        janela = tratamento._JanelaTexto(self.p.nota._texto, "Nota")
        try:
            self.assertIn("VAC LOCK", janela.texto.text())
            self.assertIn("BEXIGA", janela.texto.text())
        finally:
            janela.deleteLater()

    def test_sem_nota_a_palavra_nao_promete_clique(self):
        """Título que promete clique e não faz nada é pior que título mudo."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("TORAX", [self._PNG], "")])
        self.assertFalse(self.p.nota.tem_nota())
        self.assertEqual(self.p.nota.cursor().shape(), Qt.ArrowCursor)

    def test_a_procedencia_nao_repete_o_nome_da_montagem(self):
        """Com uma montagem só, o nome da nota não acrescenta nada ao que as
        fotos mostram; com várias, ele já está no seletor."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("TORAX", [self._PNG], "nota")])
        self.assertNotIn("TORAX", self.p._procedencia_fotos)

    def test_a_procedencia_sai_do_cartao_e_vai_para_a_janela_do_clique(self):
        """Pedido do usuário em 22/08/2026: "fica mais clean".

        Ela não pode DESAPARECER — um corte de duas versões atrás mostra um
        alvo que já não é o do tratamento em curso, e imagem sem procedência é
        a pior espécie de imagem numa tela de conferência. O que muda é
        QUANDO: no gesto de olhar de perto, que é quando alguém decide alguma
        coisa por ela. Sob duas miniaturas de 90px ela era lida de raspão.
        """
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        origem = "Da ficha elaborada em 20/08/2026 · versão 2"
        self.p.definir_imagens(self._PNG, self._PNG, origem)
        # Nada no rosto do cartão escreve a procedência…
        rotulos = [w.text() for w in self.p._cartao_imagens.findChildren(QLabel)]
        self.assertNotIn(origem, rotulos)
        # …e a janela do clique a traz, nas DUAS imagens.
        for img in (self.p.img_cortes, self.p.img_dvh):
            janela = tratamento._JanelaImagem(self._PNG, "Corte", img._procedencia)
            try:
                self.assertEqual(janela.procedencia.text(), origem)
                self.assertTrue(janela.procedencia.isVisibleTo(janela))
            finally:
                _destruir(janela)

    def test_sem_procedencia_a_janela_nao_reserva_a_linha(self):
        """Rótulo vazio sob a imagem é espaço reservado por via das dúvidas —
        e ainda promete um dado que não existe."""
        janela = tratamento._JanelaImagem(self._PNG, "Corte", "")
        try:
            self.assertFalse(janela.procedencia.isVisibleTo(janela))
        finally:
            _destruir(janela)

    def test_a_nota_leva_a_procedencia_da_montagem_que_esta_na_tela(self):
        """O paciente com DUAS montagens (9000003CEL: META e CRÂNIO) troca de
        posicionamento no seletor, e a nota que se abre é a daquela. Sem a
        procedência junto, ler a nota da montagem errada não deixa rastro."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("META", [self._PNG] * 4, "deitar de bruços")])
        self.assertIn("+2", self.p.nota._procedencia)

    def test_um_posicionamento_so_nao_oferece_escolha(self):
        """Combo de item único é uma pergunta que já tem resposta."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_fotos([("TORAX", [self._PNG], "")])
        self.assertFalse(self.p.combo_setup.isVisible())

    def test_termino_previsto_conta_o_ritmo_e_pula_o_fim_de_semana(self):
        """A MESMA conta da faixa "terminam esta semana" do painel: duas contas
        para a mesma data, na mesma tela, é como ela perde a confiança."""
        t = tratamento_db.Tratamento(
            entregues=1, previstas=3, frequencia="Dias Alternados",
            sessoes=[_sessao(20, fracao=1)])
        # Quinta 20/08 + 2 frações × 2 dias úteis = quarta 26/08.
        self.assertEqual(t.previsao_de_fim(date(2026, 8, 21)),
                         date(2026, 8, 26))
        self.p.mostrar(t)
        valores = [v.val.text() for v in self.p._valores]
        self.assertTrue(any("/" in v and len(v) == 10 for v in valores),
                        f"nenhuma data na fileira: {valores}")

    def test_curso_concluido_nao_preve_termino(self):
        """Prever o fim do que já acabou é ruído."""
        t = tratamento_db.Tratamento(
            entregues=10, previstas=10, sessoes=[_sessao(20, fracao=10)])
        self.assertIsNone(t.previsao_de_fim(date(2026, 8, 21)))
        self.p.mostrar(t)
        self.assertNotIn("TÉRMINO PREVISTO",
                         [v.rot.text().upper() for v in self.p._valores])

    def test_sem_denominador_nao_ha_data(self):
        """Sem saber quantas faltam não há previsão — só chute, e chute não
        entra numa tela de conferência."""
        t = tratamento_db.Tratamento(entregues=5, previstas=0,
                                     sessoes=[_sessao(20, fracao=5)])
        self.assertIsNone(t.previsao_de_fim(date(2026, 8, 21)))

    def test_frequencia_ganha_cartao_proprio(self):
        """Ela já estava na linha da prescrição, mas some no meio dela — e é o
        campo que responde "o paciente vem amanhã?"."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=2, previstas=10, frequencia="Uma Vez por Dia",
            sessoes=[_sessao(20, fracao=2)]))
        rotulos = [v.rot.text().upper() for v in self.p._valores]
        valores = [v.val.text() for v in self.p._valores]
        self.assertIn("FREQUÊNCIA", rotulos)
        self.assertIn("Uma Vez por Dia", valores)

    def test_as_portas_do_fim_seguem_a_alternancia_INTEIRA(self):
        """Fundo e TEXTO, não só o fundo.

        A cor do valor mora noutra folha, aplicada no nascimento do cartão:
        trocar ``tom`` e repintar só o quadro deixava as três portas (PDF,
        Checklist, Campos) com texto verde sobre fundo neutro — a alternância
        "verde branco verde branco" quebrava justamente no fim da fileira, que
        é onde ela é mais visível.
        """
        from isocentro.interface import estilo as st

        self.p.mostrar(tratamento_db.Tratamento(
            entregues=2, previstas=10, frequencia="Uma Vez por Dia",
            sessoes=[_sessao(20, fracao=2)]))
        for b in (self.p.btn_pdf, self.p.btn_checklist, self.p.btn_campos):
            esperado = st.ACAO if b.tom == "azul" else st.TEXTO
            self.assertIn(esperado, b.val.styleSheet(),
                          f"{b.rot.text()}: texto não acompanhou o tom {b.tom}")
            fundo = st.ACAO_FUNDO if b.tom == "azul" else st.FUNDO_CAMPO
            self.assertIn(fundo, b.styleSheet())

    def test_controle_respiratorio_so_quando_HA(self):
        """DIBH e gating mudam a montagem na mesa e o tempo da sessão; não
        aparecer é a resposta para a maioria dos tratamentos."""
        sem = tratamento_db.Tratamento(entregues=2, previstas=10,
                                       sessoes=[_sessao(20, fracao=2)])
        self.p.mostrar(sem)
        self.assertNotIn("CONTROLE RESPIRATÓRIO",
                         [v.rot.text().upper() for v in self.p._valores])
        com = tratamento_db.Tratamento(entregues=2, previstas=10,
                                       respiratorio="DIBH",
                                       sessoes=[_sessao(20, fracao=2)])
        self.p.mostrar(com)
        self.assertIn("CONTROLE RESPIRATÓRIO",
                      [v.rot.text().upper() for v in self.p._valores])

    def test_botao_do_pdf_apagado_sem_ficha(self):
        """Botão aceso que só avisa que não deu é a promessa que este projeto
        não faz — o motivo vai no tooltip."""
        self.p.definir_pdf("")
        self.assertFalse(self.p.btn_pdf._ativo)
        self.assertEqual(self.p.btn_pdf.cursor().shape(), Qt.ArrowCursor)
        self.assertIn("não tem ficha elaborada", self.p.btn_pdf.toolTip())
        self.p.definir_pdf(r"C:\x\FICHA.pdf")
        self.assertTrue(self.p.btn_pdf._ativo)
        self.assertEqual(self.p.btn_pdf.cursor().shape(),
                         Qt.PointingHandCursor)

    def test_o_pdf_tem_a_forma_dos_cartoes_de_valor(self):
        """"Mesma formatação" herdada, não copiada: copiada à mão, ela vira
        parecida na primeira vez que ``ui.Valor`` mudar."""
        from isocentro.interface import ui
        self.assertIsInstance(self.p.btn_pdf, ui.Valor)

    def test_a_fileira_alterna_as_cores(self):
        """"Verde branco verde branco" — e por POSIÇÃO, porque metade dos
        cartões é condicional: preso ao assunto, sumir a parada deixava dois
        vizinhos da mesma cor."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=2, previstas=10, dose_entregue_cgy=400,
            frequencia="Uma Vez por Dia", dose_dia="200",
            sessoes=[_sessao(20, fracao=2)]))
        tons = [v.tom for v in self.p._valores]
        self.assertEqual(tons, ["azul", "neutro"] * (len(tons) // 2)
                         + (["azul"] if len(tons) % 2 else []))

    def test_parada_so_aparece_quando_HOUVE_parada(self):
        """"Sem paradas" é a resposta na maioria dos tratamentos, e um cartão
        que quase sempre diz a mesma coisa deixa de ser lido."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=2, previstas=10,
            sessoes=[_sessao(20, fracao=2), _sessao(19, fracao=1)]))
        rotulos = [v.rot.text().upper() for v in self.p._valores]
        self.assertNotIn("PARADA", rotulos)

    def test_com_parada_o_cartao_volta(self):
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=2, previstas=10,
            sessoes=[_sessao(20, fracao=2), _sessao(3, fracao=1)]))
        rotulos = [v.rot.text().upper() for v in self.p._valores]
        self.assertIn("PARADA", rotulos)

    def test_clicar_na_imagem_abre_em_tamanho_grande(self):
        """Cortes de 250 px num cartão de canto não servem para conferir nada —
        eles dizem QUE existem, e o clique é que mostra."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_imagens(self._PNG, self._PNG, "Da ficha de 20/08")
        janela = tratamento._JanelaImagem(self._PNG, "Cortes")
        try:
            self.assertFalse(janela.pixmap_vazio())
        finally:
            janela.deleteLater()

    def test_moldura_vazia_nao_promete_clique(self):
        """O cursor de mão é a promessa de que o clique faz algo; numa moldura
        sem imagem essa promessa é falsa."""
        self.p.definir_imagens()
        self.assertEqual(self.p.img_cortes.cursor().shape(), Qt.ArrowCursor)
        self.p.definir_imagens(self._PNG, self._PNG, "x")
        self.assertEqual(self.p.img_cortes.cursor().shape(),
                         Qt.PointingHandCursor)

    def test_sem_ficha_elaborada_o_cartao_SOME(self):
        """Paciente cuja ficha nunca passou por este programa é o caso comum —
        e um par de molduras vazias prometeria imagem que não existe."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_imagens()
        self.assertFalse(self.p._cartao_imagens.isVisible())

    def test_limpar_nao_deixa_imagem_do_paciente_anterior(self):
        """Pelo mesmo motivo da 3×4: imagem de outro paciente nesta tela mente
        com mais força que qualquer campo."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=1, previstas=3, sessoes=[_sessao(20, fracao=1)]))
        self.p.definir_imagens(self._PNG, self._PNG, "Da ficha de 20/08")
        self.p.limpar()
        self.assertFalse(self.p._cartao_imagens.isVisible())
        self.assertFalse(self.p.img_cortes.tem_imagem())

    def test_a_prescricao_aparece_com_o_sitio(self):
        """Pedido em 21/08/2026: o quadro mostra o que ACONTECEU, e ter ao lado
        o que foi PRESCRITO deixa comparar os dois sem abrir a capa."""
        t = tratamento_db.Tratamento(
            entregues=7, previstas=15,
            prescricao="Mama, esquerda: Mama + FSC E 40,05Gy@15fx  ·  "
                       "15 frações - diária",
            sessoes=[_sessao(19, fracao=7)])
        self.p.mostrar(t)
        self.assertTrue(self.p.rx.isVisible())
        self.assertIn("Mama, esquerda", self.p.rx.text())

    def test_dose_por_plano_quando_os_alvos_sao_DIFERENTES(self):
        """Pedido em 21/08/2026 (paciente 9000010CEL): dois planos tratando
        juntos são alvos diferentes, e dose a alvos diferentes não se soma —
        um número só de "dose entregue" ali não quer dizer nada."""
        t = tratamento_db.Tratamento(
            entregues=1, previstas=3, juntos=2,
            dose_entregue_cgy=900, dose_prescrita_cgy=2700,
            doses=[tratamento_db.DoseDoPlano(1, "sMEDIAST_DB", 900, 2700),
                   tratamento_db.DoseDoPlano(2, "sHILO-D_DIB", 800, 2400)],
            sessoes=[_sessao(20, fracao=1)])
        self.p.mostrar(t)
        rotulos = [v.rot.text().upper() for v in self.p._valores]
        self.assertIn("DOSE SMEDIAST_DB", rotulos)
        self.assertIn("DOSE SHILO-D_DIB", rotulos)

    def test_dose_igual_nos_dois_planos_e_do_CURSO(self):
        """Se o DW devolve o mesmo número para todos os planos, ele é do curso.
        Repeti-lo por plano faria a tela afirmar que cada alvo recebeu o
        total — o erro oposto ao que se está corrigindo."""
        doses = [tratamento_db.DoseDoPlano(1, "A", 900, 2700),
                 tratamento_db.DoseDoPlano(2, "B", 900, 2700)]
        self.assertFalse(tratamento_db.doses_distintas(doses))
        t = tratamento_db.Tratamento(
            entregues=1, previstas=3, juntos=2, dose_entregue_cgy=900,
            doses=doses, sessoes=[_sessao(20, fracao=1)])
        self.p.mostrar(t)
        rotulos = [v.rot.text().upper() for v in self.p._valores]
        self.assertIn("DOSE ENTREGUE", rotulos)

    def test_sem_prescricao_casada_o_campo_nao_aparece(self):
        """Vazio aqui SIGNIFICA "não há prescrição deste curso" — rótulo "Rx"
        sozinho prometeria um dado que não existe. E num retratamento, mostrar
        a do curso anterior poria o sítio errado ao lado das frações certas."""
        t = tratamento_db.Tratamento(entregues=7, previstas=15,
                                     sessoes=[_sessao(19, fracao=7)])
        self.p.mostrar(t)
        self.assertFalse(self.p.rx.isVisible())
        self.assertEqual(self.p.rx.text(), "")

    def test_o_cabecalho_rola_junto_com_a_lista(self):
        """Tirar o rótulo da rolagem VERTICAL foi o acerto; deixá-lo fora da
        HORIZONTAL foi o preço que veio junto.

        A linha passa da largura com facilidade (PLANO + "TBuniverSN1002" +
        dois técnicos), e aí a lista ganha barra horizontal. Com o rótulo
        parado, "MÁQUINA" fica em cima da coluna do nome — que é exatamente o
        que ele existe para não fazer.
        """
        t = tratamento_db.Tratamento(
            entregues=1, previstas=1,
            sessoes=[_sessao(19, fracao=1, quem="Elaine Luiza dos Soares",
                             maquina="TBuniverSN1002")])
        self.p.mostrar(t)
        barra = self.p.tabela.horizontalScrollBar()
        barra.setRange(0, 200)
        barra.setValue(37)
        self.assertEqual(self.p.cab_colunas.x(), tratamento._RECUO_CAB - 37)
        barra.setValue(0)
        self.assertEqual(self.p.cab_colunas.x(), tratamento._RECUO_CAB)

    def test_sem_sessao_o_cabecalho_some(self):
        """Rótulo de coluna sobre lista vazia é espaço reservado por via das
        dúvidas — e ainda promete uma tabela que não está ali."""
        self.p.limpar()
        self.assertFalse(self.p.cab_colunas.isVisible())

    # ── A aba não pode pedir mais largura que a tela ─────────────────────

    def _pares_de_tres_planos(self):
        """A fileira do paciente 9000005CEL (print do usuário em 22/08/2026)."""
        return [("Última sessão", "05/09/2025  10:12", "azul"),
                ("Dose sABD_DIBH", "4000 cGy  de 4000", "azul"),
                ("Dose sAC_9", "3000 cGy  de 3000", "azul"),
                ("Dose sLSE", "2700 cGy  de 2700", "azul"),
                ("Dose/dia", "1000 / 900 cGy", "neutro"),
                ("Frequência", "Dias Alternados", "neutro"),
                ("Maior parada", "03/09 → 05/09: 1 dia útil  (+2)", "azul")]

    def test_o_botao_de_trocar_paciente_nao_sai_da_tela(self):
        """Era o defeito relatado: "botão seleção paciente some".

        Ele não sumia — ficava FORA da janela. Os cartões de valor não
        encolhem, então a soma deles virava PISO de largura do painel; com o
        vão da coluna de imagens reservado mesmo sem imagem nenhuma, o painel
        maximizado passava a pedir 2110 px num monitor de 1920. O Qt não tem
        para onde crescer e corta o que fica à direita — que é justamente o
        "Trocar paciente", no canto do cabeçalho.
        """
        self.p.resize(1900, 950)
        self.p._estado(aviso=False, busca=False, paciente=True)
        self.p._pintar_valores(self._pares_de_tres_planos())
        self.p.resize(1900, 950)
        self.assertLessEqual(self.p.minimumSizeHint().width(), 1900)
        direita = self.p.btn_trocar.mapTo(
            self.p, self.p.btn_trocar.rect().topRight()).x()
        self.assertLessEqual(direita, self.p.width())

    def test_a_fileira_de_valores_quebra_a_linha_em_vez_de_estourar(self):
        """Numa janela estreita nada pode ficar fora nem ser cortado.

        As duas saídas erradas: espremer os cartões (a ÚLTIMA SESSÃO perde a
        hora, a dose perde o total) ou empurrar a janela. A terceira é descer
        para a linha de baixo, que é o que se mede aqui.
        """
        self.p._estado(aviso=False, busca=False, paciente=True)
        self.p._pintar_valores(self._pares_de_tres_planos())
        for largura in (1900, 1366, 1000):
            with self.subTest(largura=largura):
                self.p.resize(largura, 950)
                cartoes = self.p._valores + [self.p.btn_pdf]
                self.assertTrue(
                    all(c.geometry().right() <= largura for c in cartoes),
                    "cartão de valor terminou fora da janela")
                # Mais de uma linha: os sete cartões não cabem em 1000 px, e
                # caber sem quebrar significaria que algum foi espremido.
                if largura == 1000:
                    self.assertGreater(
                        len({c.geometry().y() for c in cartoes}), 1)

    def test_o_vao_da_coluna_de_imagens_so_existe_com_a_coluna(self):
        """Reserva de espaço vazio "por via das dúvidas" — e cara: 572 px.

        O vão alinha o fim dos cartões com o fim da lista de sessões, e por
        isso só faz sentido quando a coluna da direita está lá. O paciente sem
        fotos e sem ficha elaborada é o caso COMUM, e era ele que pagava a
        largura de uma coluna que não existia na tela dele.
        """
        self.p.definir_fotos()
        self.p.definir_imagens()
        self.assertEqual(self.p.linha_valores.vao(), 0)
        self.p.definir_imagens(cortes=b"x", origem="ficha de 01/08/2026")
        self.assertEqual(self.p.linha_valores.vao(),
                         tratamento._LARG_IMAGENS + 12)

    def _fileira_com(self, larguras, largura_total, vao=0, altura=47):
        """Uma ``_Fileira`` solta com cartões de largura conhecida."""
        from PySide6.QtCore import QRect
        from PySide6.QtWidgets import QWidget
        pai = QWidget()
        fileira = tratamento._Fileira(espaco=10, parent=pai)
        cartoes = []
        for w in larguras:
            c = QWidget(pai)
            c.setFixedSize(w, altura)
            fileira.addWidget(c)
            cartoes.append(c)
        fileira.definir_vao(vao)
        fileira.setGeometry(QRect(0, 0, largura_total, 0))
        return pai, fileira, cartoes

    def test_o_vao_e_dispensado_quando_custaria_uma_linha(self):
        """A segunda linha saía cortada pela borda do quadro (print de 23/09/2026).

        Onze cartões — três planos mais PDF, Checklist e Campos — somam ~1800 px:
        cabem na largura toda e NÃO cabem nela menos o vão da coluna de imagens
        (572 + 12). Antes o vão era margem fixa, os quatro últimos desciam para
        uma segunda linha, e o quadro, medido por uma linha só, cortava-a.
        """
        larguras = [175, 133, 173, 173, 173, 89, 157, 255, 127, 122, 104]
        pai, f, cartoes = self._fileira_com(larguras, 1868, vao=584)
        self.assertEqual(len({c.y() for c in cartoes}), 1,
                         "o vão obrigou a fileira a quebrar linha")
        pai.deleteLater()

    def test_o_vao_vale_quando_os_cartoes_cabem_com_ele(self):
        """Cabendo alinhados com a lista de sessões, o alinhamento continua."""
        pai, f, cartoes = self._fileira_com([175, 133, 173, 173], 1868, vao=584)
        self.assertLessEqual(max(c.geometry().right() for c in cartoes),
                             1868 - 584)
        pai.deleteLater()

    def test_a_altura_minima_acompanha_a_quebra_de_linha(self):
        """O Qt pergunta o mínimo sem largura; a fileira tem de responder com a
        altura das linhas que já usa, ou o cartão do quadro é espremido.
        """
        larguras = [400, 400, 400]
        pai, f, cartoes = self._fileira_com(larguras, 900)
        self.assertEqual(len({c.y() for c in cartoes}), 2)
        self.assertGreaterEqual(f.minimumSize().height(), 47 * 2 + 10)
        pai.deleteLater()

    # ── As três portas: PDF, Checklist e Campos ──────────────────────────

    def test_as_tres_portas_fecham_a_fileira_e_seguem_a_alternancia(self):
        """Pedido do usuário em 24/08/2026: dois vizinhos do "PDF Ficha Técnica".

        Elas são widgets PERMANENTES que saem e voltam ao layout a cada
        repintura (``_Fileira`` não tem ``insertWidget``). Voltando no lugar
        errado, um botão apareceria no meio dos cartões de dado; ficando fora
        da alternância azul/neutro, o "verde branco verde branco" quebraria
        justamente no fim da fileira.
        """
        self.p._estado(aviso=False, busca=False, paciente=True)
        pares = self._pares_de_tres_planos()
        self.p._pintar_valores(pares)
        n = self.p.linha_valores.count()
        ultimos = [self.p.linha_valores.itemAt(i).widget()
                   for i in range(n - 3, n)]
        self.assertEqual(ultimos, [self.p.btn_pdf, self.p.btn_checklist,
                                   self.p.btn_campos])
        self.assertEqual(n, len(pares) + 3)
        tons = [self.p.linha_valores.itemAt(i).widget().tom for i in range(n)]
        self.assertTrue(all(t == ("azul" if i % 2 == 0 else "neutro")
                            for i, t in enumerate(tons)), tons)

    def test_o_nome_que_DISTINGUE_vai_na_linha_grande(self):
        """Os três se chamam "… Ficha Técnica", e o valor é a linha em
        destaque: com "Ficha Técnica" nos três, os cartões ficariam
        indistinguíveis de relance — que é justamente como esta fileira é
        lida."""
        valores = [self.p.btn_pdf.val.text(), self.p.btn_campos.val.text()]
        self.assertEqual(len(set(valores)), 2, valores)
        self.assertEqual(self.p.btn_campos.val.text(), "Campos")

    def test_o_cartao_do_checklist_diz_o_ANDAMENTO(self):
        """"Conferido" e "por conferir" são estados diferentes, e é essa a
        pergunta que o cartão existe para responder. Um cartão que só dissesse
        "Checklist" obrigaria a abrir a janela para descobrir se havia algo a
        fazer — com o paciente na porta."""
        self.p.definir_checklist(0, 6, 0, True)
        self.assertEqual(self.p.btn_checklist.val.text(), "por conferir")
        self.p.definir_checklist(3, 6, 0, True)
        self.assertEqual(self.p.btn_checklist.val.text(), "3 de 6")
        self.p.definir_checklist(6, 6, 0, True)
        self.assertEqual(self.p.btn_checklist.val.text(), "conferido")

    def test_divergencia_ganha_a_frente_do_conferido(self):
        """Seis de seis respondidos com um "não conforme" no meio é uma
        conferência COMPLETA e um paciente que não pode subir na mesa. Dizer
        "conferido" ali seria a tela dando um aval que a conferência negou."""
        self.p.definir_checklist(6, 6, 1, True)
        self.assertIn("não conforme", self.p.btn_checklist.val.text())

    def test_sem_curso_o_checklist_fica_APAGADO_com_o_motivo(self):
        """Botão aceso significa pronto. O checklist é por curso, e sem curso
        não há a que prendê-lo — clicar só teria um aviso para dar."""
        self.p.definir_checklist(disponivel=False)
        self.assertFalse(self.p.btn_checklist._ativo)
        self.assertIn("por curso", self.p.btn_checklist.toolTip())

    def test_sem_ficha_elaborada_os_campos_ficam_apagados(self):
        self.p.definir_campos(False)
        self.assertFalse(self.p.btn_campos._ativo)
        self.assertIn("não tem ficha elaborada", self.p.btn_campos.toolTip())
        self.p.definir_campos(True)
        self.assertTrue(self.p.btn_campos._ativo)

    def test_trocar_de_paciente_APAGA_as_tres_portas(self):
        """Botão aceso apontando para a ficha do paciente anterior é a versão
        mais cara deste erro: abre o documento de outra pessoa."""
        self.p.definir_pdf("C:/x.pdf")
        self.p.definir_checklist(6, 6, 0, True)
        self.p.definir_campos(True)
        self.p.limpar()
        self.assertFalse(self.p.btn_pdf._ativo)
        self.assertFalse(self.p.btn_checklist._ativo)
        self.assertFalse(self.p.btn_campos._ativo)

    def test_trocar_de_paciente_APAGA_o_seletor_de_plano(self):
        """Pela mesma razão da 3×4 e das três portas: seletor com os planos do
        paciente anterior oferece, com o nome certo no topo, o tratamento de
        outra pessoa."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.p.limpar()
        self.assertEqual(self.p.plano_sel.count(), 0)
        self.assertIsNone(self.p._t)
        self.assertEqual(self.p._grupos, [])

    def test_a_janela_do_checklist_traz_os_itens_do_PAPEL(self):
        """Duas listas divergem, e um checklist de tela que não é o da
        contracapa passa a atestar coisa diferente da que foi assinada."""
        from isocentro.interface import checklist as ck
        j = tratamento._JanelaChecklist({}, ck.ITENS, ck.MARCAS, ck.LEGENDA)
        try:
            self.assertEqual(len(j._botoes), len(ck.ITENS) * len(ck.MARCAS))
            self.assertIn((ck.ITENS[0], "C"), j._botoes)
        finally:
            _destruir(j)

    def test_clicar_na_marca_ACESA_desmarca(self):
        """É como se desfaz um clique errado. Sem isso, a única saída seria
        deixar registrada uma conferência que ninguém quis fazer."""
        from isocentro.interface import checklist as ck
        marcas = {ck.ITENS[0]: {"marca": "C", "por": "ivone",
                                "em": "2026-08-25T10:00:00"}}
        j = tratamento._JanelaChecklist(marcas, ck.ITENS, ck.MARCAS)
        try:
            vistos = []
            j.marcou.connect(lambda i, m: vistos.append((i, m)))
            self.assertTrue(j._botoes[(ck.ITENS[0], "C")].isChecked())
            j._botoes[(ck.ITENS[0], "C")].click()
            self.assertEqual(vistos, [(ck.ITENS[0], "")])
        finally:
            _destruir(j)

    def test_as_quatro_marcas_sao_EXCLUSIVAS_na_linha(self):
        """Conforme e não-conforme no mesmo item é um estado que o papel não
        permite — e permitir aqui deixaria a tela afirmar as duas coisas."""
        from isocentro.interface import checklist as ck
        j = tratamento._JanelaChecklist(
            {ck.ITENS[0]: {"marca": "N/C"}}, ck.ITENS, ck.MARCAS)
        try:
            acesos = [m for m in ck.MARCAS
                      if j._botoes[(ck.ITENS[0], m)].isChecked()]
            self.assertEqual(acesos, ["N/C"])
        finally:
            _destruir(j)

    def test_quem_conferiu_aparece_ao_lado_do_item(self):
        """Conferência anônima não serve: "quem conferiu a lateralidade" é a
        pergunta que se faz quando algo deu errado. Sem quem, NADA — nem um
        traço: um "—" no lugar do nome se lê como "conferido por alguém".

        A data sai em dd/mm/aaaa, como todo o resto do app: o arquivo guarda
        ISO (ordenável, sem ambiguidade), a tela mostra o formato do serviço —
        e uma data em outro formato aqui se lê como dado de outra fonte.
        """
        from isocentro.interface import checklist as ck
        j = tratamento._JanelaChecklist(
            {ck.ITENS[0]: {"marca": "C", "por": "ivone",
                           "em": "2026-08-25T10:12:00"}}, ck.ITENS, ck.MARCAS)
        try:
            texto = j._assinaturas[ck.ITENS[0]].text()
            self.assertIn("ivone", texto)
            self.assertIn("25/08/2026 10:12", texto)
            self.assertEqual(j._assinaturas[ck.ITENS[1]].text(), "")
        finally:
            _destruir(j)

    def test_a_coluna_da_assinatura_cabe_a_data_inteira(self):
        """O teto é MEDIDO na fonte, e no ``showEvent`` — a folha de estilo só
        chega ao ``fontMetrics`` quando o widget é exibido.

        Medido no ``__init__``, o teto saía da fonte PADRÃO e a coluna ficava
        menor que a própria data que ela existe para acomodar; e só com
        ``setMaximumWidth`` a coluna ainda era espremida pela largura da
        janela até abaixo dela.
        """
        from isocentro.interface import checklist as ck
        j = tratamento._JanelaChecklist(
            {ck.ITENS[0]: {"marca": "C", "por": "ivone",
                           "em": "2026-08-25T10:12:00"}}, ck.ITENS, ck.MARCAS)
        try:
            j.show()
            rot = j._assinaturas[ck.ITENS[0]]
            self.assertGreaterEqual(
                rot.width(), rot.fontMetrics().horizontalAdvance("25/08/2026 10:12"))
        finally:
            _destruir(j)

    def test_a_tabela_de_campos_usa_a_MESMA_regra_do_papel(self):
        """Três armadilhas que já custaram número errado: o número do campo é a
        POSIÇÃO (não existe no feixe), o ``or ""`` engolia colimador e mesa
        ZERO (o caso comum) e o arco virava ângulo parado."""
        from isocentro.papel import ficha_pdf
        rp = {"feixes": [{"fase": 1, "ssd": 98.4, "colimador": 0, "mesa": 0,
                          "gantry": 300, "gantry_fim": 179,
                          "gantry_sentido": "CW", "um": 245.7}]}
        j = tratamento._JanelaCampos([], rp["feixes"],
                                     ficha_pdf.linhas_campos(rp))
        try:
            self.assertEqual(j.valor_na_grade("Coll"), "0,0")   # zero NÃO some
            self.assertEqual(j.valor_na_grade("Mesa"), "0,0")
            self.assertIn("300→179", j.valor_na_grade("Gantry"))
            self.assertEqual(j.valor_na_grade("SSD"), "98,4")   # vírgula
        finally:
            _destruir(j)

    def test_o_numero_do_campo_e_o_CABECALHO_da_coluna(self):
        """A linha "Campo" da folha virou cabeçalho: é a mesma informação, e
        como cabeçalho fica congelada no topo em vez de rolar junto e sumir na
        primeira linha que se desce."""
        from isocentro.papel import ficha_pdf
        rp = {"feixes": [{"fase": 1, "um": 100}, {"fase": 1, "um": 200}]}
        j = tratamento._JanelaCampos([], rp["feixes"],
                                     ficha_pdf.linhas_campos(rp))
        try:
            self.assertEqual(
                [j.tabela.horizontalHeaderItem(i).text()
                 for i in range(j.tabela.columnCount())], ["1", "2"])
            # E "Campo" não sobra como linha da grade.
            self.assertNotIn("Campo",
                             [j.tabela.verticalHeaderItem(i).text()
                              for i in range(j.tabela.rowCount())])
        finally:
            _destruir(j)

    def test_o_quadro_do_plano_sai_em_CARTOES_como_o_resto_da_aba(self):
        """Era uma linha corrida de "Rótulo: valor · Rótulo: valor": para achar
        a dose/dia lia-se a frase inteira, e é o número que se veio conferir."""
        from isocentro.papel import ficha_pdf
        j = tratamento._JanelaCampos(
            [("Gating", "Sim"), ("Plano", "sABD")], [{"fase": 1}],
            ficha_pdf.CAMPOS_LINHAS[:2])
        try:
            self.assertEqual([c.rot.text() for c in j._cartoes],
                             ["GATING", "PLANO"])
            self.assertEqual([c.texto() for c in j._cartoes],
                             ["Sim", "sABD"])
        finally:
            _destruir(j)

    def test_o_trio_de_SSD_escreve_o_eixo_em_cima_de_cada_numero(self):
        """Era um cartão comum com "90,1 / 85,3 / 84,8": o casamento
        número↔gantry ficava no rótulo, e lê-lo custava duas contagens no meio
        de uma conferência. Posição sem valor sai como ``—``, não em branco:
        com o eixo escrito em cima, a lacuna diz QUAL das três falta."""
        from isocentro.papel import ficha_pdf
        from isocentro.interface import ui
        j = tratamento._JanelaCampos(
            [("SSD TP0 (cm)", [("G0", "90,1"), ("G270", ""), ("G90", "84,8")])],
            [{"fase": 1}], ficha_pdf.CAMPOS_LINHAS[:2])
        try:
            cartao = j._cartoes[0]
            self.assertIsInstance(cartao, ui.ValorTrio)
            grade = cartao.layout().itemAt(1).layout()
            self.assertEqual(
                [grade.itemAtPosition(0, c).widget().text() for c in range(3)],
                ["G0", "G270", "G90"])
            self.assertEqual(
                [grade.itemAtPosition(1, c).widget().text() for c in range(3)],
                ["90,1", "—", "84,8"])
        finally:
            _destruir(j)

    def test_ficha_sem_campos_diz_isso_em_vez_de_uma_grade_vazia(self):
        """Tabela em branco se lê como "não carregou", e o caso é outro: a
        ficha não gravou campo nenhum."""
        from isocentro.papel import ficha_pdf
        j = tratamento._JanelaCampos([], [], ficha_pdf.CAMPOS_LINHAS)
        try:
            self.assertIn("não tem campos", j.tabela.item(0, 0).text())
        finally:
            _destruir(j)

    def test_a_grade_termina_no_ULTIMO_campo_e_nao_na_borda(self):
        """As COLUNAS dividem o espaço que sobra, e nenhuma desce abaixo do que
        escreve.

        A grade tinha a largura exata dos campos e o resto do bloco ficava
        vazio: com dois campos, 300 px de tabela e 230 px de nada ao lado — e
        vazio à direita de uma tabela se lê como coluna que não carregou. É
        desenho de TELA: no papel a grade continua parando no último campo (ver
        ``ficha_pdf._tabela_campos``), e aqui não sobra coluna vazia nenhuma —
        são as colunas reais que ficam mais largas.
        """
        from isocentro.papel import ficha_pdf
        rp = {"feixes": [{"fase": 1, "um": 100}, {"fase": 1, "um": 200}]}
        j = tratamento._JanelaCampos([], rp["feixes"],
                                     ficha_pdf.linhas_campos(rp))
        try:
            j.resize(1100, 620)
            j.show()
            # Ocupa o bloco: o que sobra são as margens da janela e do cartão.
            self.assertGreater(j.tabela.width(), j.width() - 120)
            cab = j.tabela.horizontalHeader()
            self.assertEqual(cab.sectionResizeMode(0), QHeaderView.Stretch)
            # Nenhuma coluna espremida abaixo do que escreve — espremer
            # esconderia o UM, que é o número que se confere.
            for c in range(j.tabela.columnCount()):
                self.assertGreaterEqual(cab.sectionSize(c),
                                        cab.minimumSectionSize())
            # E sem barra horizontal: com dois campos ela cabe de sobra.
            self.assertFalse(j.tabela.horizontalScrollBar().isVisible())
        finally:
            _destruir(j)

    def test_a_janela_nasce_do_tamanho_do_que_mostra(self):
        """Era 1100×620 fixo: com dois campos a grade ocupava um quarto da
        largura e o resto era deserto. Agora a largura sai do bloco mais largo
        — e com poucos campos quem manda são os trios de SSD, que não podem
        quebrar no meio."""
        from isocentro.papel import ficha_pdf
        rp = {"feixes": [{"fase": 1, "um": 100}, {"fase": 1, "um": 200}]}
        plano = [("Gating", "Sim"), ("Plano", "sABD"),
                 ("SSD TP0 (cm)", [("G0", "90,1"), ("G270", "85,3"),
                                   ("G90", "84,8")])]
        j = tratamento._JanelaCampos(plano, rp["feixes"],
                                     ficha_pdf.linhas_campos(rp))
        try:
            self.assertLess(j.width(), 700)
            # O trio inteiro na mesma linha: a janela cabe o cartão dele.
            trio = j._cartoes[-1]
            self.assertGreater(j.width(), trio.sizeHint().width())
        finally:
            _destruir(j)

    def test_os_dados_e_os_SSD_saem_em_blocos_separados(self):
        """Onze cartões e uma grade soltos na mesma coluna não diziam onde um
        assunto termina e o outro começa. Sem SSD gravado não nasce bloco
        nenhum: cartão com título e nada dentro promete um dado que a ficha não
        tem."""
        from isocentro.papel import ficha_pdf
        rp = {"feixes": [{"fase": 1, "um": 100}]}
        com = tratamento._JanelaCampos(
            [("Gating", "Sim"),
             ("SSD Iso (cm)", [("G0", "93,7"), ("G270", ""), ("G90", "")])],
            rp["feixes"], ficha_pdf.linhas_campos(rp))
        sem = tratamento._JanelaCampos([("Gating", "Sim")], rp["feixes"],
                                       ficha_pdf.linhas_campos(rp))
        try:
            self.assertIsNotNone(com.bloco_plano)
            self.assertIsNotNone(com.bloco_setup)
            self.assertIsNotNone(com.bloco_campos)
            self.assertIsNone(sem.bloco_setup)
        finally:
            _destruir(com)
            _destruir(sem)

    # (O antigo ``test_o_pdf_continua_no_fim_da_fileira`` virou
    # ``test_as_tres_portas_fecham_a_fileira_e_seguem_a_alternancia``, acima:
    # desde 24/08/2026 quem fecha a fileira são TRÊS botões, não um.)

    def test_busca_so_mostra_a_lista_quando_ha_o_que_mostrar(self):
        """Treze mil nomes em ordem alfabética não é escolha, é obstáculo.

        Antes a lista ficava na tela repetindo "digite 2 letras". Com o painel
        acima dela, isso era altura gasta para repetir o convite que o próprio
        campo já faz — a lista some, e a contagem foi para o texto de ajuda.
        """
        from isocentro.banco import capa_dados
        self.p.definir_pacientes([
            capa_dados.PacienteRef(registro="1X", nome="ANTONIO DE SOUZA"),
            capa_dados.PacienteRef(registro="2X", nome="MARIA OLIVEIRA")])
        self.p.busca.setText("s")
        self.assertFalse(self.p.lista.isVisible())
        self.assertIn("2 pacientes", self.p.busca.placeholderText())
        self.p.busca.setText("souza")
        self.assertTrue(self.p.lista.isVisible())
        self.assertEqual(self.p.lista.count(), 1)
        self.assertIn("ANTONIO", self.p.lista.item(0).text())

    # ── Cursos: o atual manda, os anteriores ficam à mão ─────────────────

    @staticmethod
    def _cursos():
        """Como o paciente real de 19/08/2026: quatro cursos, o de agora aberto."""
        return [
            tratamento_db.Curso(id=30239, nome="C4", entregues=2, previstas=3,
                                inicio=date(2026, 8, 17), fim=date(2026, 8, 19),
                                atual=True),
            tratamento_db.Curso(id=21793, nome="C3", entregues=2, previstas=2,
                                inicio=date(2024, 7, 15), fim=date(2024, 7, 17)),
            tratamento_db.Curso(id=16242, nome="C2", entregues=3, previstas=3,
                                inicio=date(2022, 12, 19), fim=date(2022, 12, 23)),
        ]

    def _com_cursos(self, i: int = 0):
        cursos = self._cursos()
        c = cursos[i]
        return tratamento_db.Tratamento(
            curso=c, cursos=cursos, entregues=c.entregues,
            previstas=c.previstas, sessoes=[_sessao(19, fracao=c.entregues)])

    def test_o_curso_atual_ja_vem_selecionado(self):
        """Escolher entre quatro cursos antes de ver o número é uma pergunta
        cuja resposta o programa já sabe."""
        self.p.mostrar(self._com_cursos(0))
        self.assertEqual(self.p.cursos.currentIndex(), 0)
        self.assertIn("EM TRATAMENTO", self.p.cursos.currentText())
        self.assertIn("●", self.p.cursos.currentText())

    def test_curso_unico_deixa_o_seletor_apagado(self):
        """O seletor APARECE sempre — é ele que responde "há histórico?" sem
        obrigar ninguém a descobrir uma lista escondida. Mas fica apagado
        quando não há para onde ir: botão aceso significa pronto.
        """
        t = self._com_cursos(0)
        t.cursos = t.cursos[:1]
        self.p.mostrar(t)
        self.assertEqual(self.p.cursos.count(), 1)
        self.assertFalse(self.p.cursos.isEnabled())
        self.assertIn("um curso só", self.p.cursos.toolTip())

    def test_com_varios_cursos_o_seletor_acende(self):
        self.p.mostrar(self._com_cursos(0))
        self.assertTrue(self.p.cursos.isEnabled())
        self.assertEqual(self.p.cursos.count(), 3)

    def test_curso_antigo_se_anuncia(self):
        """Ver "3 / 3" em corpo 64 sem saber que aquilo terminou em 2022 é o
        erro que esta tela não pode cometer.

        A identidade do curso (nome, situação, período) mora no SELETOR; este
        rótulo carrega só o aviso, que é o que o seletor não consegue gritar.
        """
        self.p.mostrar(self._com_cursos(2))
        self.assertIn("ANTERIOR", self.p.curso_rot.text())
        self.assertTrue(self.p._curso_antigo)
        self.assertIn("concluído", self.p.cursos.currentText())

    def test_curso_atual_nao_leva_aviso(self):
        self.p.mostrar(self._com_cursos(0))
        self.assertFalse(self.p.curso_rot.text())
        self.assertFalse(self.p._curso_antigo)

    def test_nome_do_plano_em_destaque(self):
        """"MAMA D BOOST" diz mais que "P2" — é como o plano é chamado.

        O nome saiu do rótulo e foi para o SELETOR em 26/08/2026, mas continua
        em destaque e continua sendo o nome do ARIA: o ``DimPlanID`` é um
        número de seis dígitos que não diz nada a quem lê.
        """
        t = self._com_cursos(0)
        t.sessoes = [_sessao(19, fracao=2, plano=72,
                             plano_nome="MAMA D BOOST")]
        self.p.mostrar(t)
        self.assertIn("MAMA D BOOST", self.p.plano_sel.currentText())

    def test_sem_nome_de_plano_o_destaque_some(self):
        """Campo sem fonte não vira rótulo vazio na tela.

        Aqui são DOIS widgets, e os dois somem juntos: seletor vazio ao lado de
        um rótulo é pior que rótulo vazio sozinho — ele promete uma escolha
        que não existe.
        """
        self.p.mostrar(self._com_cursos(0))
        self.assertFalse(self.p.plano_rot.isVisible())
        self.assertFalse(self.p.plano_sel.isVisible())

    def test_trocar_de_curso_avisa_quem_monta_a_janela(self):
        pedidos = []
        self.p.curso_escolhido.connect(lambda r, c: pedidos.append(c))
        self.p._registro = "9X"
        self.p.mostrar(self._com_cursos(0))
        self.p.cursos.setCurrentIndex(1)
        self.p._escolher_curso(1)      # ``activated``: é o GESTO que troca
        self.assertEqual(pedidos, [21793])

    def test_repintar_a_lista_nao_dispara_troca(self):
        """Marcar o curso na tela é ARRUMAR a lista, não escolher.

        Sem bloquear o sinal, montar a lista já pedia outra leitura ao banco —
        e a resposta dessa leitura remontava a lista de novo.
        """
        pedidos = []
        self.p.curso_escolhido.connect(lambda r, c: pedidos.append(c))
        self.p.mostrar(self._com_cursos(0))
        self.p.mostrar(self._com_cursos(0))
        self.assertEqual(pedidos, [])

    # ── Planos: o seletor que faltava, e o "9 / 4" ───────────────────────

    @staticmethod
    def _dois_tratamentos_no_mesmo_curso():
        """A paciente de 26/08/2026: um curso, dois tratamentos, "9 / 4".

        `C1_JAN_2026` levou uma SBRT de pulmão (`sPTV_1` + `sPTV_2`, quatro
        frações em dias alternados) e, depois, uma mandíbula (`sMANDIBULA_E`,
        cinco). O curso somou 9 frações; o `FractionsPlanned` que o DW devolveu
        para o curso foi 4, que é de um plano só. A tela dividia os dois.
        """
        sessoes = []
        for i, dia in enumerate((27, 25, 23, 20, 18), start=1):
            sessoes.append(_sessao(dia, mes=3, fracao=6 - i, plano=90,
                                   plano_previstas=5,
                                   plano_nome="sMANDIBULA_E", hora="10:32"))
        for i, dia in enumerate((13, 11, 9, 6), start=1):
            for plano, nome, hora in ((91, "sPTV_1", "11:12"),
                                      (92, "sPTV_2", "11:24")):
                sessoes.append(_sessao(dia, mes=3, fracao=5 - i, plano=plano,
                                       plano_previstas=4, plano_nome=nome,
                                       hora=hora))
        return tratamento_db.Tratamento(
            entregues=9, previstas=4, plano_atual=90,
            plano_nome="sMANDIBULA_E", plano_entregues=5, plano_previstas=5,
            juntos=1, planos=2, sessoes=sessoes)

    def test_o_curso_com_dois_tratamentos_nao_divide_9_por_4(self):
        """"9 / 4" tem a FORMA de uma conta, e quem lê de longe lê a forma.

        O numerador é do curso e o denominador é de um plano; não há leitura
        certa dessa divisão. O total some, e a linha abaixo diz por quê.
        """
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertEqual(self.p.fracao.valor.text(), "9")
        self.assertFalse(self.p.fracao.total.text())
        self.assertIn("4", self.p.pct.text())
        self.assertIn("9", self.p.pct.text())
        self.assertIn("seletor", self.p.pct.text())

    def test_sem_denominador_a_barra_nao_afirma_andamento(self):
        """Barra vazia com nove frações aplicadas diz "não começou"."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertFalse(self.p.barra.isVisible())

    def test_o_seletor_oferece_o_curso_INTEIRO_e_cada_plano(self):
        """Três itens: o curso e os dois tratamentos que ele juntou.

        O curso vem primeiro porque é ele que a aba abre — o número grande fala
        do curso desde 20/08/2026, e mudar isso esconderia o replanejamento de
        quem não abre seletor nenhum.
        """
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertEqual(self.p.plano_sel.count(), 3)
        self.assertIn("Todos", self.p.plano_sel.itemText(0))
        self.assertIn("9 frações em 2 planos",
                      self.p.plano_sel.itemText(0))
        self.assertIn("sMANDIBULA_E", self.p.plano_sel.itemText(1))
        self.assertIn("sPTV_1 + sPTV_2", self.p.plano_sel.itemText(2))
        self.assertIsNone(self.p.plano_sel.itemData(0))
        self.assertEqual(self.p.plano_sel.currentIndex(), 0)

    def test_escolhido_o_plano_o_numero_grande_e_DELE(self):
        """É para isto que o seletor existe: 5 de 5 e 4 de 4, cada um no seu."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.p._escolher_plano(1)
        self.assertEqual(self.p.fracao.valor.text(), "5")
        self.assertEqual(self.p.fracao.total.text(), "/ 5")
        self.p._escolher_plano(2)
        self.assertEqual(self.p.fracao.valor.text(), "4")
        self.assertEqual(self.p.fracao.total.text(), "/ 4")

    def test_o_plano_na_tela_diz_que_ha_curso_em_volta(self):
        """Sem isto, "4 de 4 — plano concluído" esconde as outras 5 frações."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.p._escolher_plano(2)
        self.assertIn("plano 1 de 2", self.p.planos.text())
        self.assertIn("9", self.p.planos.text())
        self.assertIn("2 planos tratam juntos", self.p.planos.text())

    def test_escolhido_o_plano_a_lista_mostra_as_sessoes_DELE(self):
        """O seletor manda no quadro INTEIRO, não só no número.

        Lista do curso embaixo de um número de plano é a mesma mistura que
        produziu o "9 / 4" — dois escopos na mesma tela sem nada dizendo qual é
        qual.
        """
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertEqual(self.p.tabela.count(), 13)
        self.p._escolher_plano(1)
        self.assertEqual(self.p.tabela.count(), 5)
        self.assertNotIn("sPTV", self.p.tabela.item(0).text())

    def test_trocar_de_plano_NAO_pede_nada_ao_banco(self):
        """As sessões já vieram todas na leitura do curso.

        Uma segunda consulta para reordenar o que está na memória é a chance de
        os dois números divergirem — e trocar de plano ficaria tão lento quanto
        trocar de curso.
        """
        pedidos = []
        self.p.curso_escolhido.connect(lambda r, c: pedidos.append(c))
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.p._escolher_plano(1)
        self.assertEqual(pedidos, [])

    def test_a_dose_do_CURSO_nao_vira_a_dose_do_plano(self):
        """Dose a alvos diferentes não se soma — e não se reaproveita.

        Com um plano na tela, o número do curso inclui o que o outro entregou a
        outro alvo. Sem dose por plano, o cartão não aparece: vazio aqui é "não
        sei", e é o que a tela tem a dizer.
        """
        t = self._dois_tratamentos_no_mesmo_curso()
        t.dose_entregue_cgy = 7800.0
        self.p.mostrar(t)
        self.assertIn("7800", " ".join([v.val.text() for v in self.p._valores]))
        self.p._escolher_plano(1)
        self.assertNotIn("7800", " ".join([v.val.text() for v in self.p._valores]))

    def test_um_plano_so_deixa_o_seletor_apagado(self):
        """O seletor APARECE sempre — é ele que nomeia o plano —, mas fica
        apagado quando não há para onde ir: botão aceso significa pronto."""
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=3, previstas=15, juntos=1, planos=1,
            sessoes=[_sessao(20, fracao=3, plano=72,
                             plano_nome="cMAMA_D2")]))
        self.assertEqual(self.p.plano_sel.count(), 1)
        self.assertFalse(self.p.plano_sel.isEnabled())
        self.assertIn("cMAMA_D2", self.p.plano_sel.currentText())
        self.assertIn("um plano só", self.p.plano_sel.toolTip())

    def test_com_um_plano_so_os_numeros_continuam_vindo_do_CURSO(self):
        """O item único guarda ``None``: o comportamento do caso comum não muda.

        As previstas do curso (do DW, que sabe que o replanejamento SUBSTITUI o
        que restava) continuam mandando; as do plano são o que o plano
        declarou, e trocar uma pela outra em silêncio mudaria o número grande de
        todo paciente da clínica por causa de uma tela nova.
        """
        self.p.mostrar(tratamento_db.Tratamento(
            entregues=3, previstas=15, juntos=1, planos=1,
            sessoes=[_sessao(20, fracao=3, plano=72, plano_previstas=25,
                             plano_nome="cMAMA_D2")]))
        self.assertEqual(self.p.fracao.total.text(), "/ 15")

    def test_escolhido_o_plano_o_SELETOR_mostra_o_plano(self):
        """Quadro falando de um plano com o seletor dizendo "Todos" é a mesma
        mistura de escopos que produziu o "9 / 4"."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.p._escolher_plano(1)
        self.assertEqual(self.p.plano_sel.currentIndex(), 1)
        self.assertIn("sMANDIBULA_E", self.p.plano_sel.currentText())

    def test_o_rotulo_vai_ao_plural_pelo_que_esta_na_TELA(self):
        """Com um plano escolhido, "PLANOS" falaria de planos que a tela deixou
        de mostrar."""
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertEqual(self.p.plano_rot.text(), "PLANOS")
        self.p._escolher_plano(1)
        self.assertEqual(self.p.plano_rot.text(), "PLANO")
        self.p._escolher_plano(2)      # sPTV_1 + sPTV_2 tratam juntos
        self.assertEqual(self.p.plano_rot.text(), "PLANOS")

    def test_o_total_que_nao_fecha_sai_em_AMBAR(self):
        """No lugar onde antes havia um "/ 4", cinza passa despercebido.

        Âmbar e não vermelho, como o aviso de curso antigo: não é erro que se
        conserte aqui — é um número do sistema que fala de outra coisa.
        """
        self.p.mostrar(self._dois_tratamentos_no_mesmo_curso())
        self.assertTrue(self.p._pct_alerta)
        self.assertIn(tratamento.st.AMBAR, self.p.pct.styleSheet())
        self.p._escolher_plano(1)
        self.assertFalse(self.p._pct_alerta)
        self.assertNotIn(tratamento.st.AMBAR, self.p.pct.styleSheet())

    def test_o_cartao_age_no_SOLTAR_e_nao_no_apertar(self):
        """Abrir a janela com o botão do mouse ainda apertado a deixa ATRÁS.

        O Windows entrega o soltar à janela que estava sob o cursor — a
        principal —, e ela sobe por cima da modal recém-aberta. Foi o que o
        usuário viu em 26/08/2026 ao clicar em "Campos": a janela abria atrás,
        e o app parecia travado (nada responde, porque há uma modal que ninguém
        vê).
        """
        cliques = []
        self.p.btn_campos.clicado.connect(lambda: cliques.append(1))
        self.p.definir_campos(True)
        self.p.btn_campos.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, self.p.btn_campos.rect().center(),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        self.assertEqual(cliques, [], "o apertar não pode abrir nada")
        _clicar(self.p.btn_campos)
        self.assertEqual(cliques, [1])

    def test_arrastar_para_fora_do_cartao_DESISTE(self):
        """Soltar fora é o que dá a chance de corrigir a mira — e no apertar
        não havia como desistir."""
        cliques = []
        self.p.btn_campos.clicado.connect(lambda: cliques.append(1))
        self.p.definir_campos(True)
        _clicar(self.p.btn_campos, dentro=False)
        self.assertEqual(cliques, [])

    def test_cartao_APAGADO_nao_responde_ao_clique(self):
        """Botão aceso significa pronto; apagado não abre nada, nem no soltar."""
        cliques = []
        self.p.btn_campos.clicado.connect(lambda: cliques.append(1))
        self.p.definir_campos(False)
        _clicar(self.p.btn_campos)
        self.assertEqual(cliques, [])

    def test_o_pop_up_nao_reserva_linha_VAZIA(self):
        """Sobrava a faixa de um item em branco embaixo da lista.

        Uma linha vazia numa lista lê-se como opção que não carregou — e o
        cálculo do Qt para a altura do pop-up erra quando a folha de estilo
        muda o tamanho do item. A altura passou a ser cravada no que a lista
        tem para mostrar.
        """
        t = self._dois_tratamentos_no_mesmo_curso()
        t.cursos = self._cursos()
        t.curso = t.cursos[0]
        self.p.mostrar(t)
        for combo in (self.p.cursos, self.p.plano_sel):
            self.assertTrue(combo.count(), "o seletor tem de ter itens")
            moldura = 2 * combo.view().frameWidth()
            self.assertEqual(
                combo.view().height(),
                combo.count() * tratamento._ALTURA_ITEM + moldura,
                f"sobra no pop-up de {combo.count()} itens")

    def test_lista_longa_para_no_TETO_e_rola(self):
        """Vinte cursos não viram um pop-up da altura da tela."""
        cursos = [tratamento_db.Curso(id=i, nome=f"C{i}", entregues=1,
                                      previstas=1, inicio=date(2026, 3, 1),
                                      atual=(i == 1)) for i in range(1, 21)]
        t = self._com_cursos(0)
        t.cursos = cursos
        self.p.mostrar(t)
        teto = self.p.cursos.maxVisibleItems() * tratamento._ALTURA_ITEM
        self.assertEqual(self.p.cursos.view().height(),
                         teto + 2 * self.p.cursos.view().frameWidth())

    def test_o_pop_up_reserva_a_altura_de_CADA_item(self):
        """O seletor de cursos abria com dois itens e meio.

        Com folha de estilo, o Qt calcula a altura do pop-up pelo ``sizeHint``
        dos itens; o ``min-height`` da folha pinta grande dentro do espaço
        pequeno que já foi reservado, e o último item saía cortado ao meio —
        justamente na data, que é o que distingue um curso do outro.
        """
        self.p.mostrar(self._com_cursos(0))
        alturas = {self.p.cursos.itemData(i, Qt.SizeHintRole).height()
                   for i in range(self.p.cursos.count())}
        self.assertEqual(alturas, {tratamento._ALTURA_ITEM})

    def test_o_pop_up_cabe_o_texto_INTEIRO(self):
        """A lista nasce com a largura do combo FECHADO, e ele elide.

        Aberta, ela repetia o texto cortado — que é o que se abriu a lista para
        ler.
        """
        self.p.mostrar(self._com_cursos(0))
        fm = self.p.cursos.fontMetrics()
        maior = max(fm.horizontalAdvance(self.p.cursos.itemText(i))
                    for i in range(self.p.cursos.count()))
        self.assertGreaterEqual(self.p.cursos.view().minimumWidth(), maior)

    def test_escolher_avisa_quem_monta_a_janela(self):
        """A tela não fala com o banco: pede por sinal e recebe pronto."""
        from isocentro.banco import capa_dados
        recebidos = []
        self.p.paciente_escolhido.connect(
            lambda r, n: recebidos.append((r, n)))
        self.p.definir_pacientes(
            [capa_dados.PacienteRef(registro="9X", nome="MARIA OLIVEIRA")])
        self.p.busca.setText("maria")
        self.p.lista.setCurrentRow(0)
        self.assertEqual(recebidos, [("9X", "MARIA OLIVEIRA")])


if __name__ == "__main__":
    unittest.main()


class _VigiaDeJanelaSolta(QObject):
    """Denuncia todo widget SEM PAI que aparece — no Qt, ele é uma JANELA.

    Diálogos e pop-ups de combo ficam de fora: esses são janelas de propósito.
    O painel da aba entra em ``ignorar`` pelo mesmo motivo — no teste ele é
    montado sem pai, e no app é filho da janela principal.
    """

    def __init__(self, ignorar=()):
        super().__init__()
        self._ignorar = tuple(ignorar)
        self.soltas: list = []

    def eventFilter(self, obj, e):  # noqa: N802 — assinatura do Qt
        # ``& Qt.Popup`` NÃO serve para perguntar "isto é um pop-up?": a
        # constante inclui o bit ``Qt.Window``, então TODA janela dá verdadeiro
        # e o vigia passava a aprovar justamente o que existe para pegar (o
        # teste ficou verde com o defeito de volta). O tipo de janela mora no
        # ``WindowType_Mask``, e é ele que se compara.
        janela = (obj.windowFlags() & Qt.WindowType_Mask
                  if isinstance(obj, QWidget) else None)
        if (e.type() == QEvent.Show and isinstance(obj, QWidget)
                and obj.parent() is None
                and not isinstance(obj, QDialog)
                and janela not in (Qt.Popup, Qt.ToolTip, Qt.SplashScreen)
                and obj not in self._ignorar):
            self.soltas.append(
                f"{type(obj).__name__}"
                + (f" {obj.text()!r}" if hasattr(obj, "text") else ""))
        return False

    def __enter__(self):
        _APP.installEventFilter(self)
        return self

    def __exit__(self, *_):
        _APP.removeEventFilter(self)
        return False


class TestBuscaPeloRegistro(unittest.TestCase):
    """A busca da Ficha Virtual acha pelo ID, não só pelo nome.

    O campo já dizia "nome ou registro" — o que faltava era teste: a Capa, que
    faz a MESMA pergunta, não dizia, e o usuário concluiu em 31/08/2026 que
    nenhuma das duas aceitava o ID. Afordância sem teste é a que some numa
    limpeza de código sem ninguém perceber.
    """

    def setUp(self):
        self._verificado = tratamento_db.VERIFICADO_EM
        tratamento_db.VERIFICADO_EM = "01/01/2026"
        self._servidor = os.environ.get("ISOCENTRO_DB_SERVIDOR")
        # Tirar o nome NOVO antes de gravar o antigo: ele tem precedência no
        # ``ambiente.ler`` e venceria o ``SERVIDOR_DE_TESTE`` daqui.
        self._servidor_novo = os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        os.environ["ISOCENTRO_DB_SERVIDOR"] = "SERVIDOR_DE_TESTE"
        self.p = tratamento.PainelFichaVirtual()
        from isocentro.banco import capa_dados
        self.p.definir_pacientes([
            capa_dados.PacienteRef(nome="Antonio Carlos de Souza",
                                   registro="9000004CEL"),
            capa_dados.PacienteRef(nome="Maria Oliveira",
                                   registro="9000018ANA")])

    def tearDown(self):
        _destruir(self.p)
        tratamento_db.VERIFICADO_EM = self._verificado
        for nome, valor in (("ISOCENTRO_DB_SERVIDOR", self._servidor),
                            ("ISOCENTRO_DB_SERVIDOR", self._servidor_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    def _achados(self):
        return [self.p.lista.item(i).text()
                for i in range(self.p.lista.count())]

    def test_acha_pelo_registro(self):
        self.p.busca.setText("9000004CEL")
        self.assertEqual(len(self._achados()), 1)
        self.assertIn("Antonio", self._achados()[0])

    def test_acha_por_um_pedaco_do_registro(self):
        # O pedaço sai do registro da fixture. Ver o gêmeo no
        # `test_capa_tela.py`: a pseudonimização de 10/09/2026 quebrou os dois.
        self.p.busca.setText("018")
        self.assertIn("Maria", self._achados()[0])

    def test_o_campo_diz_que_aceita_o_registro(self):
        self.p.busca.setText("")
        self.assertIn("registro", self.p.busca.placeholderText())


class TestNenhumaJanelaSolta(unittest.TestCase):
    """A "mini tela que pisca" — relatada em 26/08/2026 ao abrir os Campos.

    ``QLabel(texto)`` sem pai mais ``setVisible(True)`` ANTES do ``addWidget``
    é uma janela de 107×16 abrindo no meio do monitor e sumindo quando o layout
    lhe dá um pai. O piscar é o sintoma leve; o grave é a estação lenta, onde
    ela fica visível o bastante para roubar o foco do que se estava fazendo.

    O teste é da ABA INTEIRA, e não da linha corrigida: o defeito é de padrão,
    não daquele rótulo — e é por uma tela nova que ele volta.
    """

    def setUp(self):
        self._verificado = tratamento_db.VERIFICADO_EM
        tratamento_db.VERIFICADO_EM = "01/01/2026"
        self._servidor = os.environ.get("ISOCENTRO_DB_SERVIDOR")
        # Tirar o nome NOVO antes de gravar o antigo: ele tem precedência no
        # ``ambiente.ler`` e venceria o ``SERVIDOR_DE_TESTE`` daqui.
        self._servidor_novo = os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        os.environ["ISOCENTRO_DB_SERVIDOR"] = "SERVIDOR_DE_TESTE"

    def tearDown(self):
        tratamento_db.VERIFICADO_EM = self._verificado
        for nome, valor in (("ISOCENTRO_DB_SERVIDOR", self._servidor),
                            ("ISOCENTRO_DB_SERVIDOR", self._servidor_novo)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    def test_montar_as_telas_da_aba_nao_abre_janela_nenhuma(self):
        from isocentro.interface import checklist as ck
        from isocentro.papel import ficha_pdf

        painel = tratamento.PainelFichaVirtual()
        janelas: list = []
        try:
            painel.show()
            _APP.processEvents()
            with _VigiaDeJanelaSolta(ignorar=(painel,)) as vigia:
                janelas = [
                    tratamento._JanelaCampos(
                        [("Plano", "sMAMA_D"), ("Frações", "15"),
                         ("SSD medido", [("X", "1"), ("Y", "2"), ("Z", "3")])],
                        [{"nome": "C1"}], ficha_pdf.linhas_campos({}),
                        "Da ficha elaborada", painel),
                    tratamento._JanelaChecklist(
                        {}, ck.ITENS, ck.MARCAS, ck.LEGENDA, parent=painel),
                    tratamento._JanelaTexto("uma nota", "Nota", "de onde",
                                            painel),
                    tratamento._JanelaImagem(TestTela._PNG, "Cortes", "daqui",
                                             painel),
                ]
                _APP.processEvents()
                self.assertEqual(vigia.soltas, [])
        finally:
            for j in janelas:
                _destruir(j)
            _destruir(painel)


class TestNomeProprio(unittest.TestCase):
    """Nome de paciente em caixa alta, baixa e misturada na mesma lista.

    O cadastro traz "CARMEN CRISTINA NACIFE DE SA" ao lado de "Francisco Job do
    Nascimento". Numa lista, a mistura é lida como dado de origens diferentes —
    e caixa alta ainda ocupa mais largura para dizer o mesmo.
    """

    def _f(self, texto):
        from isocentro.banco import capa_dados
        return capa_dados.como_nome_proprio(texto)

    def test_caixa_alta_vira_nome(self):
        self.assertEqual(self._f("NEUZA TAVARES DE ABREU"),
                         "Neuza Tavares de Abreu")

    def test_conectivo_fica_minusculo_no_meio(self):
        """"De Abreu" não é português. "de Abreu" é."""
        self.assertEqual(self._f("LUCIA RODRIGUES ROSA DO CARMO"),
                         "Lucia Rodrigues Rosa do Carmo")

    def test_conectivo_no_comeco_continua_maiusculo(self):
        """Nome que COMEÇA com a partícula não a rebaixa."""
        self.assertTrue(self._f("DA SILVA JUNIOR").startswith("Da "))

    def test_hifen_e_apostrofo_capitalizam_dos_dois_lados(self):
        """Ali a partícula não é conectivo — é parte do sobrenome."""
        self.assertEqual(self._f("MARIA D'ALMEIDA SILVA-NETO"),
                         "Maria D'Almeida Silva-Neto")

    def test_iniciais_sobrevivem(self):
        self.assertEqual(self._f("j. p. lima"), "J. P. Lima")

    def test_vazio_continua_vazio(self):
        """Campo sem fonte nasce vazio — não vira espaço nem placeholder."""
        self.assertEqual(self._f(""), "")
        self.assertEqual(self._f(None), "")

    def test_login_da_maquina_vira_nome(self):
        """A máquina assina com o login; "ivone.silva" no meio de "Santos"
        parece dado de outra origem."""
        self.assertEqual(tratamento_db._quem_legivel("ivone.silva"),
                         "Ivone Lúcia da Silva")

    def test_sobrenome_do_login_nao_e_o_sobrenome_da_pessoa(self):
        """Trocar ponto por espaço acertava a aparência e ERRAVA a pessoa:
        "washington.drangel" saía "Washington Drangel" e "waleska.santos" saía
        "Waleska Santos" — num serviço que tem uma Vanessa e uma Waleska."""
        self.assertEqual(tratamento_db._quem_legivel("washington.drangel"),
                         "Washington de Souza Rocha")
        self.assertEqual(tratamento_db._quem_legivel("waleska.santos"),
                         "Waleska de Sousa Medeiros")
        self.assertEqual(tratamento_db._quem_legivel("vanessa.dias"),
                         "Vanessa Carneiro Marques")

    def test_contas_da_mesma_pessoa_dao_o_mesmo_nome(self):
        """"gisele" (console), "gisele.silva" e "gisele.silveira" são a mesma
        radioterapeuta; três nomes na coluna viram três pessoas na leitura de
        quem tratou o paciente."""
        nomes = {tratamento_db._quem_legivel(c)
                 for c in ("gisele", "gisele.silva", "gisele.silveira")}
        self.assertEqual(nomes, {"Gisele Kelly Pinheiro Silva"})

    def test_etiqueta_do_console_nao_e_nome_de_gente(self):
        """Visto na tela em 20/08/2026, sessão de 10/08: "Tatiane.ferraz Criado Por
        Treatapp". O banco entrega SOBRENOME e NOME colados, e nas contas
        sincronizadas o nome é a etiqueta que o console escreveu."""
        self.assertEqual(
            tratamento_db._quem_legivel("tatiane.ferraz Criado por TreatApp"),
            "Tatiane da Costa Ferraz")
        self.assertEqual(
            tratamento_db._quem_legivel("wagner.sousa CRIADO POR TREATAPP"),
            "Wagner Cesar de Sousa")

    def test_so_a_etiqueta_nao_identifica_ninguem(self):
        """Sem nada além dela, o campo fica VAZIO e a tela diz "(não
        informado)" — inventar uma pessoa a partir de texto de sistema é o pior
        desfecho possível."""
        self.assertEqual(tratamento_db._quem_legivel("Criado por TreatApp"), "")

    def test_o_nome_manda_no_sobrenome(self):
        """"Soares" nu é a Michele, mas "Soares Mauricio" é o Mauricio. Sem essa
        ordem, quem divide o sobrenome com uma conta sem nome perdia todas as
        suas sessões para ela."""
        self.assertEqual(tratamento_db._quem_legivel("Soares Mauricio"),
                         "Mauricio Henrique Soares")
        self.assertEqual(tratamento_db._quem_legivel("silva Gisele Kelly"),
                         "Gisele Kelly Pinheiro Silva")
        self.assertEqual(
            tratamento_db._quem_legivel("Camargo Josiane Fernandes"),
            "Josiane Fernandes Camargo")

    def test_o_nome_do_MEIO_nao_decide(self):
        """Só o segundo pedaço é o nome. O "Carneiro" de "Souza Renata Carneiro
        de" é chave da Vanessa: olhando todos os pedaços, a sessão da Renata ia
        para ela."""
        self.assertEqual(
            tratamento_db._quem_legivel("Souza Renata Carneiro de"),
            "Renata Carneiro de Souza")

    def test_texto_livre_nao_e_sequestrado_por_um_sobrenome(self):
        """Só o PRIMEIRO pedaço vale como sobrenome — é o que o banco põe na
        frente. Sem essa amarra, qualquer texto terminado num sobrenome
        conhecido virava a pessoa dele: "Maria Santos" seria "Jonas Souza
        Santos"."""
        self.assertEqual(tratamento_db._quem_legivel("Maria Santos"),
                         "Maria Santos")
        self.assertEqual(tratamento_db._quem_legivel("J. Santos"), "J. Santos")

    def test_os_dois_pedacos_tem_de_falar_da_mesma_pessoa(self):
        """O sobrenome de uma e o nome de outra não formam ninguém.

        "Pereira" é chave da Jussara e "Leandro" é do Leandro Carvalhal: quem
        chegasse assim — contratação nova que divide os dois com gente da
        tabela — saía com a sessão atribuída ao Leandro. Numa coluna que existe
        para dizer QUEM tratou, é o defeito que ela deveria impedir.
        """
        self.assertEqual(tratamento_db._quem_legivel("Pereira Leandro Andrade"),
                         "Pereira Leandro Andrade")
        self.assertEqual(tratamento_db._quem_legivel("Silva Maria Jose"),
                         "Silva Maria Jose")
        self.assertEqual(tratamento_db._quem_legivel("Costa Bruno"),
                         "Costa Bruno")

    def test_sobrenome_conhecido_com_o_nome_batendo_ainda_vale(self):
        """A conferência não pode custar quem a tabela ACERTA: "ronaldo" não é
        chave de ninguém, mas "Ronaldo Castilho" é o nome inteiro do dono do
        "castilho" — e é assim que a conta do console chega."""
        self.assertEqual(tratamento_db._quem_legivel("Castilho Ronaldo"),
                         "Ronaldo Castilho")
        self.assertEqual(tratamento_db._quem_legivel("Almeida Telma"),
                         "Telma Almeida")

    def test_sobrenome_de_outro_console_nao_precisa_estar_no_nome(self):
        """A mesma pessoa tem sobrenome DIFERENTE em cada console: "Hayashi"
        no 600CD, e o nome que a ficha imprime é "Mario Sergio". Conferir só
        pelo nome inteiro rejeitaria a combinação certa — as duas chaves são
        contas da mesma pessoa, e é isso que vale."""
        self.assertEqual(tratamento_db._quem_legivel("Hayashi Mario"),
                         "Mario Sergio")
        self.assertEqual(tratamento_db._quem_legivel("Lucia Ivone"),
                         "Ivone Lúcia da Silva")

    def test_conta_de_fisico_usa_a_grafia_da_ficha(self):
        """``mario``, ``mariohenrique`` e ``mario.hayashi`` são o mesmo físico
        (dito pelo usuário). O login sugeriria "Mario Hayashi"; a ficha
        imprime "Mario Sergio", e dois nomes para a mesma pessoa em dois
        documentos do mesmo paciente é o que se está evitando."""
        nomes = {tratamento_db._quem_legivel(c)
                 for c in ("mario", "mariohenrique", "mario.hayashi")}
        self.assertEqual(nomes, {"Mario Sergio"})
        self.assertIn("Mario Sergio", equipe.FISICOS)

    def test_sobrenome_do_console_e_nome_de_gente(self):
        """"Rangel" no banco não é login nenhum: é o SOBRENOME cadastrado de
        ``milton`` no console 4D. Sem a tabela, a coluna misturava sobrenome
        solto com login e parecia dado de duas origens."""
        self.assertEqual(tratamento_db._quem_legivel("Rangel"), "Milton Rangel")
        self.assertEqual(tratamento_db._quem_legivel("Teles"),
                         "Debora Teles de Gouveia")

    def test_sobrenome_de_duas_contas_SEM_NOME_nao_vira_nome_de_uma(self):
        """Duas contas com o mesmo sobrenome só disputam o sobrenome NU se as
        duas tiverem o campo Nome vazio — a que tem nome nunca chega nua.
        "Souza" é o caso que sobrou: ``renata.souza`` (6EX) e ``waleska``
        (600CD), as duas sem nome."""
        for chave in tratamento_db.SOBRENOMES_AMBIGUOS:
            self.assertNotIn(chave, tratamento_db.RADIOTERAPEUTAS, chave)
        self.assertEqual(tratamento_db._quem_legivel("Souza"), "Souza")

    def test_sobrenome_nu_e_de_quem_nao_tem_nome_cadastrado(self):
        """Dito pelo usuário em 20/08/2026 — "Soares é a Michele Soares" — e o
        cadastro diz por quê: a conta ``michele`` tem o Nome vazio nos dois
        consoles, e o Mauricio, que divide o sobrenome, chega como "Soares
        Mauricio". Mesma coisa para Ivone × Gisele e Diego × Josiane."""
        self.assertEqual(tratamento_db._quem_legivel("Soares"), "Michele Soares")
        self.assertEqual(tratamento_db._quem_legivel("Silva"),
                         "Ivone Lúcia da Silva")
        self.assertEqual(tratamento_db._quem_legivel("Camargo"),
                         "Diego José Camargo Costa")

    def test_sobrenome_de_uma_conta_so_vira_o_nome_inteiro(self):
        """O que o usuário viu em 20/08 e devolveu: a tela mostrava "Santos" e
        "Carneiro" soltos porque eu contava homônimos pelo NOME COMPLETO da
        equipe. O banco copia o campo Sobrenome do console, e ali cada um destes
        está numa conta só — a Fabiana ter "Dos Santos" no nome não cria
        ambiguidade, porque ela não tem conta com esse sobrenome."""
        self.assertEqual(tratamento_db._quem_legivel("Santos"),
                         "Jonas Souza Santos")
        self.assertEqual(tratamento_db._quem_legivel("Carneiro"),
                         "Vanessa Carneiro Marques")
        self.assertEqual(tratamento_db._quem_legivel("Sousa"),
                         "Waleska de Sousa Medeiros")
        self.assertEqual(tratamento_db._quem_legivel("Costa"),
                         "Elaine Luiza dos Soares")

    def test_nenhuma_chave_serve_a_duas_pessoas(self):
        """O dicionário fica com a ÚLTIMA e não reclama: quem acrescentasse uma
        conta já usada trocaria o nome de outra pessoa em silêncio."""
        todas = [c for _, chaves in tratamento_db._CONTAS for c in chaves]
        repetidas = sorted({c for c in todas if todas.count(c) > 1})
        self.assertEqual(repetidas, [])
        self.assertEqual(len(todas), len(tratamento_db.RADIOTERAPEUTAS))

    def test_chave_da_tabela_e_sempre_minuscula(self):
        """A busca é feita em caixa baixa: chave com maiúscula entra na tabela e
        nunca é encontrada — some sem erro nenhum."""
        for chave in tratamento_db.RADIOTERAPEUTAS:
            self.assertEqual(chave, chave.lower(), chave)

    def test_conta_que_nao_e_gente_sai_como_esta_cadastrada(self):
        """"RPA103" normalizado vira "Rpa103"; não é nome próprio."""
        self.assertEqual(tratamento_db._quem_legivel("rpa103"), "RPA103")
        self.assertEqual(tratamento_db._quem_legivel("clinicafisica"),
                         "Clinica Física")

    def test_dominio_nao_esconde_o_nome(self):
        """Assinatura qualificada não pode escapar da tabela e sair como
        "Clinica\\wagner sousa"."""
        self.assertEqual(tratamento_db._quem_legivel("CLINICA\\wagner.sousa"),
                         "Wagner Cesar de Sousa")

    def test_login_fora_da_tabela_ainda_aparece(self):
        """Contratação nova não pode sumir da coluna: a tabela acerta o nome,
        não decide quem existe."""
        self.assertEqual(tratamento_db._quem_legivel("fulano.deoliveira"),
                         "Fulano Deoliveira")

    def test_nome_ja_escrito_nao_perde_o_ponto(self):
        """"J. Santos" é nome, não login: virar "J Santos" seria estragá-lo."""
        self.assertEqual(tratamento_db._quem_legivel("J. Santos"), "J. Santos")


class TestContagemDeCursos(unittest.TestCase):
    """Retratamento muda conduta, e a lista não dizia nada sobre isso."""

    def test_zero_significa_nao_consegui_contar(self):
        """E não "nenhum curso" — o paciente está NA lista de em tratamento,
        então ele tem pelo menos um. Zero só pode ser falha de leitura."""
        e = tratamento_db.EmTratamento(registro="1X", nome="X")
        self.assertEqual(e.cursos_total, 0)

    def test_falha_ao_contar_nao_derruba_a_lista(self):
        """A contagem é CONTEXTO, não a razão de a tela existir."""
        consultar = capa_db_modulo._consultar

        def explodir(*_a, **_k):
            raise capa_db_modulo.FalhaDeLeitura("derrubada")

        capa_db_modulo._consultar = explodir
        linhas = [tratamento_db.EmTratamento(registro="1X", nome="X")]
        try:
            tratamento_db._contar_cursos(linhas)      # não pode levantar
        finally:
            capa_db_modulo._consultar = consultar
        self.assertEqual(linhas[0].cursos_total, 0)

    def test_o_registro_do_banco_vem_com_espaco_e_a_chave_tem_de_bater(self):
        """``PatientId`` é ``char`` no DW e volta com espaços à direita.

        A linha da lista guarda o registro APARADO (``capa_db._txt``); a
        contagem vinha crua do banco, e a comparação falhava em TODAS as linhas
        de uma vez — a coluna sumia inteira, sem erro nenhum, que é como um
        dado silencioso vira "o banco não tem isso".
        """
        consultar = capa_db_modulo._consultar
        capa_db_modulo._consultar = lambda *_a, **_k: [("1X   ", 3)]
        linhas = [tratamento_db.EmTratamento(registro="1X", nome="X")]
        try:
            tratamento_db._contar_cursos(linhas)
        finally:
            capa_db_modulo._consultar = consultar
        self.assertEqual(linhas[0].cursos_total, 3)

    def test_lista_gigante_nao_vira_IN_gigante(self):
        """Um IN com milhares de parâmetros é plano de execução ruim; a coluna
        fica vazia em vez de a consulta travar a tela."""
        muitos = [tratamento_db.EmTratamento(registro=f"{i}X", nome="X")
                  for i in range(tratamento_db._MAX_NA_CONTAGEM + 1)]
        tratamento_db._contar_cursos(muitos)          # não consulta nada
        self.assertTrue(all(e.cursos_total == 0 for e in muitos))


class TestPrescricaoDoCurso(unittest.TestCase):
    """O sítio e a prescrição no quadro — e por que eles sumiam."""

    def _com(self, prescricoes, curso="C1_AGO_2026"):
        disponivel = tratamento_db.disponivel
        ler = capa_db_modulo.prescricoes_do_paciente
        tratamento_db.disponivel = lambda: True
        capa_db_modulo.prescricoes_do_paciente = lambda _r: prescricoes
        try:
            return tratamento_db.prescricao_do_curso("1X", curso)
        finally:
            capa_db_modulo.prescricoes_do_paciente = ler
            tratamento_db.disponivel = disponivel

    @staticmethod
    def _rx(curso="", site="Mama, esquerda", desc="Mama E 40,05Gy@15fx"):
        return capa_dados_modulo.Prescricao(
            site=site, descricao=desc, curso=curso, fracoes="15",
            frequencia="Uma Vez por Dia")

    def test_casa_pelo_curso(self):
        texto = self._com([self._rx(curso="C0_ANTIGO", site="Próstata"),
                           self._rx(curso="C1_AGO_2026")])
        self.assertIn("Mama, esquerda", texto)
        self.assertNotIn("Próstata", texto)

    def test_prescricao_UNICA_aparece_mesmo_sem_vinculo_de_curso(self):
        """O ``DimCourseID`` da ``FactPatientPrescription`` é opcional, e o
        ``LEFT JOIN`` devolve curso nulo. Casando só por ele, a linha ficava
        vazia em paciente que TEM prescrição aprovada — visto pelo usuário em
        21/08/2026. Campo que some sem motivo aparente é pior que campo
        ausente: quem lê conclui que o dado não existe no sistema.

        Com uma só prescrição no prontuário não há o que confundir.
        """
        self.assertIn("Mama, esquerda", self._com([self._rx()]))

    def test_duas_sem_vinculo_ficam_VAZIAS(self):
        """Num retratamento, herdar a do curso antigo poria o sítio errado ao
        lado das frações certas — e é o sítio que faz quem lê acreditar que
        está olhando o paciente certo."""
        self.assertEqual(
            self._com([self._rx(site="Próstata"), self._rx(site="Mama D")]),
            "")

    def test_falha_de_leitura_nao_derruba_o_quadro(self):
        def explodir(_r):
            raise capa_db_modulo.FalhaDeLeitura("derrubada")

        disponivel = tratamento_db.disponivel
        ler = capa_db_modulo.prescricoes_do_paciente
        tratamento_db.disponivel = lambda: True
        capa_db_modulo.prescricoes_do_paciente = explodir
        try:
            self.assertEqual(tratamento_db.prescricao_do_curso("1X", "C1"), "")
        finally:
            capa_db_modulo.prescricoes_do_paciente = ler
            tratamento_db.disponivel = disponivel


class TestDiagnosticoNoApp(unittest.TestCase):
    """O diagnóstico tem de existir ONDE o problema acontece.

    A caixa de erro mandava rodar tools/diagnostico_db.py — pasta que NÃO vai
    no pacote. Ou seja: mandava quem está na clínica abrir um arquivo que não
    existe naquela máquina.
    """

    @staticmethod
    def _diagnosticar_com_porta_recusada(*args, **kw):
        """``diagnosticar`` com a porta RECUSANDO sem ir à pilha TCP.

        A recusa de verdade custa 2,04 s no Windows (ver
        ``scp_falso.conexao_que_falha``). Era esse o resíduo de ~2 s de cada
        teste desta classe — e não a enumeração de drivers do ``pyodbc``, como
        o checkpoint de 14/09 tinha nomeado sem cronometrar: ela custa 6 ms. O
        que estes testes provam é a PARADA e o TEXTO, não a pilha.
        """
        from tests import scp_falso

        recusa = ConnectionRefusedError(10061, "recusou (dublê do teste)")
        with scp_falso.conexao_que_falha(recusa):
            return capa_db_modulo.diagnosticar(*args, **kw)

    def test_sem_servidor_diz_que_falta_apontar(self):
        """Isolado de QUALQUER servidor apontado nesta estação.

        ``diagnosticar("")`` cai em ``capa_db.servidor()``, que lê o
        ``config_servico.json`` — e nesta máquina ele existe. Sem apontar
        ``ISOCENTRO_CONFIG`` para uma pasta vazia, o teste mediria a estação em
        vez do código.
        """
        import tempfile
        antes = {k: os.environ.get(k)
                 for k in ("ISOCENTRO_CONFIG", "ISOCENTRO_DB_SERVIDOR",
                           "ISOCENTRO_DB_SERVIDOR")}
        os.environ["ISOCENTRO_CONFIG"] = tempfile.mkdtemp(prefix="cfg_vazia_")
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        # Os DOIS nomes: desde 09/09/2026 o ``capa_db`` lê pelo ``ambiente.ler``
        # e o ``ISOCENTRO_DB_SERVIDOR`` tem PRECEDÊNCIA — tirar só o antigo
        # deixaria o banco apontado numa estação que já migrou, e o teste
        # falharia só nela.
        os.environ.pop("ISOCENTRO_DB_SERVIDOR", None)
        try:
            passos = capa_db_modulo.diagnosticar("")
        finally:
            for chave, valor in antes.items():
                if valor is None:
                    os.environ.pop(chave, None)
                else:
                    os.environ[chave] = valor
        self.assertFalse(all(ok for _n, ok, _r in passos))
        self.assertIn("Sistema", passos[-1][2])

    def test_para_na_primeira_camada_que_falha(self):
        """Continuar depois da rede fechada só produziria erro derivado.

        O que se afirma aqui é o INVARIANTE — nada depois da primeira falha —,
        e não que a camada seja a "Rede": sem pyodbc ou sem driver ODBC o
        diagnóstico para antes disso, e a versão anterior deste teste falhava
        justamente na estação em que o diagnóstico mais serve.

        E o alvo é ``127.0.0.1`` numa porta fechada, não um nome inventado: o
        nome fazia DNS de verdade e demorava o que o resolvedor da estação
        quisesse. E nem a porta fechada vai à rede: custava 2 s de repetição
        de SYN no Windows (ver ``_diagnosticar_com_porta_recusada``).
        """
        passos = self._diagnosticar_com_porta_recusada("127.0.0.1", porta=1)
        falhas = [i for i, (_n, ok, _r) in enumerate(passos) if ok is False]
        self.assertEqual(len(falhas), 1)
        self.assertEqual(falhas[0], len(passos) - 1)

    def test_instancia_nomeada_nao_para_na_porta_1433(self):
        """Instância nomeada usa porta DINÂMICA, e ``conexao()`` não manda porta
        nenhuma quando o alvo tem barra invertida.

        Parando ali, o diagnóstico gritava "isto é REDE" — mandando abrir
        chamado de firewall — e escondia o login e a permissão, que é onde a
        resposta está, num servidor em que o app entra sem tropeço.
        """
        # GUARDA e devolve a constante, nunca ``del``: ``modulo.X = v`` grava no
        # __dict__ do módulo, e o ``del`` sumiria com a ORIGINAL para o resto do
        # processo. Mesmo remédio do ``ACSE_SEGUNDOS`` do DICOM, em 14/09/2026.
        #
        # O limite curto não enfraquece o que se afirma aqui, que é o TEXTO do
        # recado ("porta dinâmica") e o diagnóstico ter SEGUIDO adiante da rede.
        # Com os 6 s cravados, o ``pyodbc.connect`` da instância NOMEADA
        # esperava o SQL Browser que nunca responde: 8,6 s, o teste mais caro
        # dos três módulos do banco. Um segundo prova o mesmo — e não ZERO, que
        # para o pyodbc significa "sem tempo-limite", o oposto do que se quer.
        limite = capa_db_modulo.TEMPO_LIMITE_S
        capa_db_modulo.TEMPO_LIMITE_S = 1
        try:
            passos = self._diagnosticar_com_porta_recusada(
                "127.0.0.1\\SQLEXPRESS", porta=1)
        finally:
            capa_db_modulo.TEMPO_LIMITE_S = limite
        rede = [(n, ok, r) for n, ok, r in passos if n == "Rede"]
        if not rede:
            self.skipTest("sem pyodbc ou sem driver ODBC nesta estação")
        self.assertIsNone(rede[0][1])
        self.assertIn("porta dinâmica", rede[0][2])
        # E o diagnóstico SEGUIU: a entrada no banco é que decide.
        self.assertNotEqual(passos[-1][0], "Rede")

    def test_recusa_por_identidade_nao_e_chamada_de_permissao(self):
        """Confundir as duas manda a pessoa abrir o chamado errado e esperar
        dias por uma resposta que não resolve."""
        texto = capa_db_modulo._explicar_recusa(
            "[Microsoft][ODBC SQL Server Driver]Não é possível gerar o "
            "contexto SSPI", "MAQUINA" + chr(92) + "usuario")
        self.assertIn("IDENTIDADE", texto)
        self.assertIn("não permissão", texto)

    def test_banco_fechado_para_a_conta_E_permissao(self):
        """4060: o servidor aceitou quem eu sou e recusou o que eu posso."""
        texto = capa_db_modulo._explicar_recusa("Cannot open database (4060)", "x")
        self.assertIn("permissão", texto)
        self.assertIn("db_datareader", texto)

    def test_a_string_testada_e_a_MESMA_que_o_app_usa(self):
        """Testar uma conexão diferente da real daria um "OK" que não vale."""
        texto = capa_db_modulo._texto_de_conexao("SQL Server", "SRV")
        self.assertIn("SERVER=SRV,1433", texto)
        self.assertIn("Trusted_Connection=yes", texto)
        # O driver antigo rejeita estes dois com "atributo inválido".
        self.assertNotIn("TrustServerCertificate", texto)


@unittest.skipIf(tratamento is None, "PySide6 indisponível")
class TestChecklistQueFalhaAoGravar(unittest.TestCase):
    """Falhar a gravação não pode APAGAR da tela o que já está conferido.

    A janela do checklist recebe de volta o que ficou no disco a cada clique.
    Quando esse caminho levantava, a janela recebia ``{}`` — e a lista aberta
    na frente de quem confere se esvaziava, enquanto o arquivo (e o cartão,
    relido logo em seguida) continuavam com as marcas. Numa conferência
    pré-tratamento, tela e disco discordando é o pior desfecho: alguém remarca
    o que já estava marcado, ou confia num aval que não vê.
    """

    class _FichaVirtualFalsa:
        def __init__(self):
            self.recebido = None
            self.avisos = []

        def registro_na_tela(self):
            return "1X"

        def curso_na_tela(self):
            return 1

        def atualizar_checklist(self, marcas):
            self.recebido = marcas

        def mostrar_status(self, msg, erro=False):
            self.avisos.append((msg, erro))

    def _janela(self):
        """O controle de verdade sobre a tela falsa: sem janela nenhuma."""
        from isocentro.interface import controle_virtual

        j = controle_virtual.ControleFichaVirtual(
            TestChecklistQueFalhaAoGravar._FichaVirtualFalsa(),
            {"usuario": "ivone"})
        j.cartao = 0

        def cartao(_registro=""):
            j.cartao += 1
        j.checklist_cartao = cartao
        return j

    def test_a_tela_recebe_o_DISCO_e_nao_um_dicionario_vazio(self):
        from isocentro.interface import checklist as ck

        gravado = {ck.ITENS[0]: {"marca": "C", "por": "ivone",
                                 "em": "2026-08-25T10:00:00"}}
        marcar, ler = ck.marcar, ck.ler
        ck.marcar = lambda *_a, **_k: (_ for _ in ()).throw(
            OSError("compartilhamento fora do ar"))
        ck.ler = lambda *_a, **_k: gravado
        try:
            j = self._janela()
            j.checklist_marcar(ck.ITENS[1], "C")
            self.assertEqual(j.ficha_virtual.recebido, gravado)
            self.assertTrue(j.ficha_virtual.avisos[-1][1], "não avisou do erro")
        finally:
            ck.marcar, ck.ler = marcar, ler

    def test_se_nem_a_releitura_vai_a_tela_fica_COMO_ESTA(self):
        """Desfazer marcação na tela é pior que não atualizar — o recado de
        erro já saiu, e a pessoa decide o que fazer com a folha na mão."""
        from isocentro.interface import checklist as ck

        marcar, ler = ck.marcar, ck.ler
        ck.marcar = lambda *_a, **_k: (_ for _ in ()).throw(OSError("x"))
        ck.ler = lambda *_a, **_k: (_ for _ in ()).throw(OSError("x"))
        try:
            j = self._janela()
            j.checklist_marcar(ck.ITENS[1], "C")
            self.assertIsNone(j.ficha_virtual.recebido)
            self.assertTrue(j.ficha_virtual.avisos[-1][1])
        finally:
            ck.marcar, ck.ler = marcar, ler


class TestRecusaDaClinica(unittest.TestCase):
    """18456 e SSPI são OPOSTOS, e confundi-los custou dois dias.

    SSPI: a identidade não chegou a ser formada (máquina fora do domínio).
    18456: a identidade chegou INTEIRA e o servidor a recusou.

    Um manda entrar no domínio; o outro manda abrir chamado de liberação.
    """

    ERRO_CLINICA = ("[28000] [Microsoft][ODBC SQL Server Driver][SQL Server]"
                    "Login failed for user 'REDE" + chr(92) * 2
                    + "geovani.pena'. (18456)")

    def test_18456_manda_abrir_chamado_de_liberacao(self):
        texto = capa_db_modulo._explicar_recusa(
            self.ERRO_CLINICA, "REDE" + chr(92) + "geovani.pena")
        self.assertIn("AUTORIZAÇÃO", texto)
        self.assertIn("db_datareader", texto)
        self.assertIn("variandw", texto)

    def test_18456_nao_manda_mexer_no_dominio(self):
        """Era o erro de leitura: procurar problema de domínio quando o que
        faltava era uma linha no chamado."""
        texto = capa_db_modulo._explicar_recusa(self.ERRO_CLINICA, "X")
        self.assertNotIn("IDENTIDADE", texto)
        self.assertNotIn("fora do domínio", texto)

    def test_sspi_continua_mandando_o_contrario(self):
        texto = capa_db_modulo._explicar_recusa("contexto SSPI", "X")
        self.assertIn("IDENTIDADE", texto)
        self.assertNotIn("db_datareader", texto)

    def test_o_recado_sugere_grupo_e_nao_conta(self):
        """Por conta, cada pessoa nova precisa de um chamado — e vê a capa cair
        na reserva sem entender por quê."""
        texto = capa_db_modulo._explicar_recusa(self.ERRO_CLINICA, "X")
        self.assertIn("GRUPO", texto)


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.

@unittest.skipIf(tratamento is None, "PySide6 indisponível")
class TestGrupoMedico(unittest.TestCase):
    """A caixa do médico e o botão Grupo Médico — pedido em 22/09/2026.

    Antes era uma caixa só, com caixinhas dentro da lista suspensa, fazendo as
    duas coisas. O que se fixa aqui é a separação: a caixa escolhe UM, o botão
    soma OUTROS, e o que sai continua sendo a lista que a consulta entende —
    vazia para "todos", com o principal na frente.
    """

    MEDICOS = [
        tratamento_db.Medico(nome="Ana Prado", bruto="Prado, Ana"),
        tratamento_db.Medico(nome="Bruno Lima", bruto="Lima, Bruno"),
        tratamento_db.Medico(nome="Célia Rocha", bruto="Rocha, Célia"),
    ]

    def setUp(self):
        self.s = tratamento._SeletorMedicos()

    def tearDown(self):
        _destruir(self.s)

    def _brutos(self):
        return [m.bruto for m in self.s.escolhidos()]

    def test_sem_escolha_e_todos_os_medicos(self):
        """Vazio significa "todos" para a consulta, e a tela tem de dizer isso
        com palavras — foi o estado de quem não marcava nada na caixa antiga."""
        self.s.definir(self.MEDICOS, [])
        self.assertEqual(self._brutos(), [])
        self.assertEqual(self.s.combo.currentText(),
                         tratamento._ComboMedico.TODOS)

    def test_com_todos_o_botao_do_grupo_fica_desligado(self):
        """Somar colegas a "todos" não muda nada, e um botão que não muda nada
        é um convite a achar que mudou."""
        self.s.definir(self.MEDICOS, [])
        self.assertFalse(self.s.btn_grupo.isEnabled())
        self.assertIn("Todos", self.s.btn_grupo.toolTip())

    def test_um_medico_escolhido_sai_sozinho(self):
        self.s.definir(self.MEDICOS, ["Lima, Bruno"])
        self.assertEqual(self._brutos(), ["Lima, Bruno"])
        self.assertTrue(self.s.btn_grupo.isEnabled())

    def test_o_grupo_soma_ao_principal_e_ele_vem_na_frente(self):
        """A ordem não é enfeite: é ela que o ``QSettings`` grava e que diz,
        na volta, quem é o principal."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        self.assertEqual(self._brutos(), ["Lima, Bruno", "Prado, Ana"])

    def test_o_botao_diz_quantos_entraram(self):
        """Um grupo montado semanas atrás continua valendo; sem o número, a
        pessoa lê a lista como se fosse só a dela."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        self.assertIn("+1", self.s.btn_grupo.text())
        self.assertIn("Ana Prado", self.s.btn_grupo.toolTip())

    def test_trocar_o_principal_para_alguem_do_grupo_nao_o_duplica(self):
        """Ele entraria duas vezes no ``IN`` da consulta e duas na etiqueta."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        self.s.combo.setCurrentIndex(
            self.s.combo.findData(self.MEDICOS[0]))
        self.assertEqual(self._brutos(), ["Prado, Ana"])

    def test_voltar_para_todos_desfaz_o_grupo(self):
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        self.s.combo.setCurrentIndex(0)
        self.assertEqual(self._brutos(), [])
        self.assertFalse(self.s.btn_grupo.isEnabled())

    def test_medico_que_saiu_do_servico_nao_filtra_para_sempre(self):
        """Gravado no ``QSettings`` e ausente da lista do banco, ele ficaria
        cortando a lista sem aparecer em lugar nenhum da tela."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Sumiu, Quem"])
        self.assertEqual(self._brutos(), ["Lima, Bruno"])

    def test_a_escolha_antiga_de_varios_vira_principal_mais_grupo(self):
        """A caixa antiga gravava uma lista SEM hierarquia. Quem atualizar o
        app abre a aba com a mesma lista de pacientes de antes."""
        self.s.definir(self.MEDICOS, ["Rocha, Célia", "Prado, Ana",
                                      "Lima, Bruno"])
        self.assertEqual(self.s.combo.currentText(), "Célia Rocha")
        self.assertEqual(self._brutos(),
                         ["Rocha, Célia", "Prado, Ana", "Lima, Bruno"])

    def test_o_principal_nao_aparece_para_desmarcar_no_dialogo(self):
        """Desmarcável, ele criaria um estado em que a caixa diz um nome e a
        lista mostra a agenda de outro."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno"])
        d = tratamento._DialogGrupoMedicos(
            self.MEDICOS, self.MEDICOS[1], [], self.s)
        try:
            nomes = [d.lista.item(i).text() for i in range(d.lista.count())]
        finally:
            _destruir(d)
        self.assertEqual(nomes, ["Ana Prado", "Célia Rocha"])

    def test_limpar_no_dialogo_desmarca_todos(self):
        d = tratamento._DialogGrupoMedicos(
            self.MEDICOS, self.MEDICOS[1], ["Prado, Ana", "Rocha, Célia"],
            self.s)
        try:
            d._limpar()
            self.assertEqual(d.escolhidos(), [])
        finally:
            _destruir(d)

    def _abrir_grupo(self, resposta, marcar=()):
        """Abre o Grupo Médico pelo caminho de verdade, sem janela modal.

        ``exec_`` postiço, e não o diálogo montado à mão: é o ``abrir_grupo``
        que decide o que fazer com a resposta, e é ele que o botão chama. Um
        ``exec_`` de verdade travaria a suíte esperando alguém clicar.
        """
        original = tratamento._DialogGrupoMedicos.exec

        def falso(propria):
            for i in range(propria.lista.count()):
                item = propria.lista.item(i)
                alvo = item.data(Qt.UserRole).bruto in marcar
                item.setCheckState(Qt.Checked if alvo else Qt.Unchecked)
            return resposta

        tratamento._DialogGrupoMedicos.exec = falso
        try:
            self.s.abrir_grupo()
        finally:
            tratamento._DialogGrupoMedicos.exec = original

    def test_cancelar_o_dialogo_nao_mexe_no_grupo(self):
        """Quem marcou cinco colegas e desistiu tem de voltar ao que tinha."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        avisos = []
        self.s.mudou.connect(lambda: avisos.append(1))
        self._abrir_grupo(QDialog.Rejected, marcar={"Rocha, Célia"})
        self.assertEqual(self._brutos(), ["Lima, Bruno", "Prado, Ana"])
        self.assertEqual(avisos, [])

    def test_confirmar_o_dialogo_repoe_a_lista_uma_vez(self):
        """O aviso é o que manda a janela reler o banco: nenhum, a lista fica
        mentindo; dois, ela lê duas vezes o que demora segundos."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno"])
        avisos = []
        self.s.mudou.connect(lambda: avisos.append(1))
        self._abrir_grupo(QDialog.Accepted, marcar={"Rocha, Célia"})
        self.assertEqual(self._brutos(), ["Lima, Bruno", "Rocha, Célia"])
        self.assertEqual(avisos, [1])

    def test_confirmar_sem_mudar_nada_nao_manda_reler_o_banco(self):
        """Abrir, olhar e dizer OK é o gesto mais comum, e ele não mudou nada:
        a lista inteira vem do servidor, e recarregá-la à toa é a tela parada
        por segundos sem motivo."""
        self.s.definir(self.MEDICOS, ["Lima, Bruno", "Prado, Ana"])
        avisos = []
        self.s.mudou.connect(lambda: avisos.append(1))
        self._abrir_grupo(QDialog.Accepted, marcar={"Prado, Ana"})
        self.assertEqual(avisos, [])


@unittest.skipIf(tratamento is None, "PySide6 indisponível")
class TestColunaDoMedicoNaLista(unittest.TestCase):
    """De quem é cada paciente, quando a agenda é de mais de um médico."""

    def _linha(self, **kw):
        base = dict(registro="1X", nome="Fulano de Tal", entregues=1,
                    previstas=5, ultima=date(2026, 9, 21))
        base.update(kw)
        return tratamento_db.EmTratamento(**base)

    def test_com_um_medico_so_a_coluna_nao_existe(self):
        """Ela repetiria o mesmo nome em vinte e cinco linhas e empurraria o
        resto para a direita sem dizer nada."""
        linha = tratamento._LinhaPainel(
            self._linha(medico="Ana Prado", medicos_total=1))
        try:
            self.assertFalse(hasattr(linha, "medico"))
        finally:
            _destruir(linha)

    def test_na_agenda_em_conjunto_a_coluna_mostra_o_medico(self):
        linha = tratamento._LinhaPainel(
            self._linha(medico="Ana Prado", medicos_total=1),
            mostrar_medico=True)
        try:
            self.assertEqual(linha.medico.text(), "Ana Prado")
        finally:
            _destruir(linha)

    def test_paciente_com_dois_medicos_nao_afirma_exclusividade(self):
        """O banco devolve UM dos vinculados; o nome sozinho mentiria por
        omissão justamente na tela em que o médico procura os seus."""
        linha = tratamento._LinhaPainel(
            self._linha(medico="Ana Prado", medicos_total=2),
            mostrar_medico=True)
        try:
            self.assertIn("+1", linha.medico.text())
            self.assertIn("mais de um médico", linha.medico.toolTip())
        finally:
            _destruir(linha)

    def test_sem_medico_vinculado_a_linha_continua_na_lista(self):
        """Sumir da lista é o pior desfecho possível — por isso o ``LEFT JOIN``
        no SQL, e por isso o traço aqui."""
        linha = tratamento._LinhaPainel(self._linha(), mostrar_medico=True)
        try:
            self.assertEqual(linha.medico.text(), "—")
        finally:
            _destruir(linha)


from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


class TestAliasDoOncologistFlag(unittest.TestCase):
    """``OncologistFlag`` é do VÍNCULO paciente↔médico, não do médico.

    Ela mora em ``DWH.DimPatientDoctor``; ``DWH.DimDoctor`` não a tem — as duas
    listagens de coluna da sonda (``tools/mapear_dw.py``, 23/09/2026) provam.
    Qualificada com o alias do médico, o SQL Server recusa a consulta INTEIRA
    ("Invalid column name 'OncologistFlag'", 207) e a aba Virtual não lista
    ninguém: foi o que a tela mostrou naquele dia, com o log repetindo o 207 a
    cada tentativa.

    O erro só aparece contra o banco REAL — o banco local devolve o que já foi
    gravado e nunca prepara a consulta —, então nenhum teste de dado o pegaria.
    Este lê o texto do SQL, que é onde o defeito mora.
    """

    # (módulo, nome do SQL) de tudo que menciona a coluna.
    FONTES = (
        ("isocentro.banco.tratamento_db", "_SQL_EM_TRATAMENTO"),
        ("isocentro.banco.tratamento_db", "_SQL_EM_TRATAMENTO_TODOS"),
        ("isocentro.banco.tratamento_db", "_SQL_MEDICOS"),
        ("isocentro.banco.tratamento_db", "_SQL_MEDICO_DO_PACIENTE"),
        ("isocentro.banco.capa_db", "_SQL_MEDICO"),
        ("isocentro.banco.agenda_db", "_SQL_AGENDA_DO_DIA"),
        ("isocentro.banco.agenda_db", "_SQL_AGENDA_DO_PERIODO"),
    )

    def _sqls(self):
        import importlib

        for modulo, nome in self.FONTES:
            sql = getattr(importlib.import_module(modulo), nome, None)
            if sql and "OncologistFlag" in sql:
                yield f"{modulo}.{nome}", sql

    def test_o_alias_e_o_de_dimpatientdoctor(self):
        import re

        achou = False
        for onde, sql in self._sqls():
            achou = True
            m = re.search(r"DWH\.DimPatientDoctor\s+(\w+)", sql)
            self.assertIsNotNone(
                m, f"{onde}: usa OncologistFlag sem juntar DimPatientDoctor")
            esperado = m.group(1)
            for alias in re.findall(r"(\w+)\.OncologistFlag", sql):
                self.assertEqual(
                    alias, esperado,
                    f"{onde}: {alias}.OncologistFlag — a coluna é de "
                    f"DimPatientDoctor ({esperado}), e o SQL Server recusa a "
                    f"consulta inteira com o alias errado")
        self.assertTrue(achou, "nenhum SQL com OncologistFlag — a lista envelheceu")

    def test_nenhum_sql_do_projeto_ficou_de_fora_da_lista(self):
        """Lista de fontes que envelhece calada deixa o defeito voltar por uma
        consulta nova — o mesmo buraco do ``test_loggers_app``."""
        import re
        from pathlib import Path

        raiz = Path(__file__).resolve().parent.parent / "isocentro"
        nomes = {nome for _m, nome in self.FONTES}
        for caminho in raiz.rglob("*.py"):
            texto = caminho.read_text(encoding="utf-8")
            if "OncologistFlag" not in texto:
                continue
            # O corpo de CADA SQL, delimitado pela própria string tripla —
            # recortar por tamanho fixo arrastava o SQL seguinte para dentro
            # do bloco e acusava o vizinho inocente.
            for nome, corpo in re.findall(
                    r'^(_SQL_\w+)\s*=\s*"""(.*?)"""', texto, re.M | re.S):
                if "OncologistFlag" in corpo:
                    self.assertIn(nome, nomes,
                                  f"{caminho.name}: {nome} não está em FONTES")


class TestListaDeMedicosEADaEquipe(unittest.TestCase):
    """A lista de escolha da Virtual não é a do banco, é a do serviço.

    O DW devolve quem tem paciente vinculado com ``OncologistFlag``, e ali
    entram o usuário de teste do ARIA ("Test Toast"), o cadastro do físico
    ("Fisica Fisica") e quem já saiu. Relatado pelo usuário em 23/09/2026,
    olhando a lista aberta: dos dezoito nomes, quatro não eram médicos do
    serviço.
    """

    DO_BANCO = ("Keiko Nakamura", "Fisica Fisica", "Test Toast",
                "Nicole Mayer Arruda Falcao", "Ricardo Alarcao")
    EQUIPE = ["Keiko Harumi Sato Nakamura", "Nicole Mayer Arruda Falcao",
              "Camila Sampaio"]

    def setUp(self):
        from isocentro.banco import capa_db

        self.capa_db = capa_db
        self._consultar = capa_db._consultar
        self._disponivel = tratamento_db.lista_disponivel
        self._equipe = tratamento_db._equipe_configurada
        capa_db._consultar = lambda sql, *p: [(n,) for n in self.DO_BANCO]
        tratamento_db.lista_disponivel = lambda: True
        tratamento_db._equipe_configurada = lambda: list(self.EQUIPE)

    def tearDown(self):
        # GUARDA E DEVOLVE — nunca ``del``: apagar deixaria o módulo sem a
        # função original para o resto da suíte.
        self.capa_db._consultar = self._consultar
        tratamento_db.lista_disponivel = self._disponivel
        tratamento_db._equipe_configurada = self._equipe

    def test_quem_nao_e_da_equipe_sai(self):
        nomes = [m.nome for m in tratamento_db.medicos()]
        for fora in ("Fisica Fisica", "Test Toast", "Ricardo Alarcao"):
            self.assertNotIn(fora, nomes)

    def test_grafia_diferente_ainda_e_a_mesma_pessoa(self):
        """"Keiko Nakamura" no banco e "Keiko Harumi Sato Nakamura" na equipe.
        Comparar texto igual apagaria catorze dos dezoito nomes reais."""
        nomes = [m.nome for m in tratamento_db.medicos()]
        self.assertIn("Keiko Nakamura", nomes)
        self.assertIn("Nicole Mayer Arruda Falcao", nomes)

    def test_o_bruto_do_banco_e_preservado(self):
        """É por ele que ``em_tratamento`` filtra: trocar pelo nome da equipe
        faria a escolha do médico não casar com paciente nenhum."""
        keiko = [m for m in tratamento_db.medicos() if m.nome == "Keiko Nakamura"]
        self.assertEqual(keiko[0].bruto, "Keiko Nakamura")

    def test_sem_equipe_legivel_nao_filtra_nada(self):
        """Perder a lista inteira de médicos por causa de um arquivo de apoio
        seria pior do que mostrá-la inteira."""
        tratamento_db._equipe_configurada = lambda: []
        self.assertEqual(len(tratamento_db.medicos()), len(self.DO_BANCO))
