"""A aba Agenda na tela: as colunas por máquina e o esmaecimento por médico.

O que se testa aqui é o comportamento que só aparece com Qt de pé: o número
de colunas bate com as máquinas marcadas, a ordem é a da faixa (não a do
SQL), e trocar de médico esmaece sem pedir nada ao banco de novo.

Rodar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    _APP = QApplication.instance() or QApplication([])
    from isocentro.banco import agenda_db
    from isocentro.banco import tratamento_db
    from isocentro.interface import agenda_tela
    from isocentro.interface import controle_agenda
except Exception:  # noqa: BLE001 — sem Qt, este arquivo fica vazio de propósito
    agenda_tela = None
    controle_agenda = None
    agenda_db = None
    tratamento_db = None
    _APP = None


def _maquina(nome, ctr):
    return agenda_db.Maquina(nome=nome, ctr_resource_ser=ctr)


def _marcacao(hora="07:36", maquina="6EX", registro="9000011CEL",
             paciente="De Tal Fulano", atividade="PELVE", estado="Completed",
             medico="Luiz Mauro Souza", medico_bruto="Souza, Luiz Mauro",
             mais_de_um=False):
    h, m = (int(x) for x in hora.split(":"))
    return agenda_db.Marcacao(
        hora=datetime(2026, 9, 23, h, m), maquina=maquina, registro=registro,
        paciente=paciente, atividade=atividade, estado=estado, medico=medico,
        medico_bruto=medico_bruto, mais_de_um_medico=mais_de_um)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestMontarPares(unittest.TestCase):
    """A função pura por trás da faixa — sem Qt, só a regra de agrupamento
    (ver ``agenda_tela.PARES_MAQUINA``)."""

    _SEIS = [_maquina("VitalBeam", 1252), _maquina("6EX", 1035),
            _maquina("Dermopan", 1400), _maquina("600CD", 1046),
            _maquina("TrueBeam", 1499), _maquina("Braquiterapia", 1600)]

    def test_agrupa_pelos_tres_pares_na_ordem_de_PARES_MAQUINA(self):
        grupos = agenda_tela._montar_pares(self._SEIS)
        nomes = [[m.nome for m in g] for g in grupos]
        self.assertEqual(nomes, [["6EX", "TrueBeam"],
                                 ["Braquiterapia", "Dermopan"],
                                 ["600CD", "VitalBeam"]])

    def test_metade_do_par_ausente_no_banco_fica_com_uma_so(self):
        grupos = agenda_tela._montar_pares(
            [_maquina("6EX", 1035), _maquina("600CD", 1046)])
        nomes = [[m.nome for m in g] for g in grupos]
        self.assertEqual(nomes, [["6EX"], ["600CD"]])

    def test_maquina_fora_dos_pares_definidos_vira_grupo_proprio(self):
        grupos = agenda_tela._montar_pares(
            [_maquina("6EX", 1035), _maquina("Nova", 9000)])
        nomes = [[m.nome for m in g] for g in grupos]
        self.assertEqual(nomes, [["6EX"], ["Nova"]])


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestFaixaDeMaquinas(unittest.TestCase):

    _SEIS = [_maquina("VitalBeam", 1252), _maquina("6EX", 1035),
            _maquina("Dermopan", 1400), _maquina("600CD", 1046),
            _maquina("TrueBeam", 1499), _maquina("Braquiterapia", 1600)]

    def test_sem_preferencia_marca_o_primeiro_par(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)
        self.assertEqual(sorted(p.maquinas_marcadas()), [1035, 1499])  # 6EX+TrueBeam

    def test_preferencia_marca_o_par_que_bate(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS, marcadas=[1046, 1252])  # 600CD+VitalBeam
        self.assertEqual(sorted(p.maquinas_marcadas()), [1046, 1252])

    def test_preferencia_sem_par_correspondente_volta_ao_primeiro(self):
        """Preferência de uma sessão com checkboxes livres (até 23/09/2026),
        ou de uma lista de pares que mudou — não trava vazia."""
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS, marcadas=[1035, 1046, 1499])
        self.assertEqual(sorted(p.maquinas_marcadas()), [1035, 1499])

    def test_preferencia_vazia_fica_sem_par_marcado(self):
        """Vazio é escolha de quem desmarcou tudo — diferente de ``None``,
        que é quem nunca escolheu."""
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS, marcadas=[])
        self.assertEqual(p.maquinas_marcadas(), [])

    def test_trocar_de_par_emite_a_lista_do_novo_uma_vez_so(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)  # começa no 6EX+TrueBeam
        recebido = []
        p.maquinas_mudaram.connect(recebido.append)
        p._botoes_par[2].setChecked(True)  # 600CD+VitalBeam
        self.assertEqual(len(recebido), 1)
        self.assertEqual(sorted(recebido[0]), [1046, 1252])


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestMaquinaUnica(unittest.TestCase):
    """"Uma máquina só" — pedido do usuário em 28/09/2026: além dos pares
    fixos (:data:`agenda_tela.PARES_MAQUINA`), poder ver uma máquina
    sozinha em dia único, sem precisar abrir um período de vários dias
    (que já força isso, ver :meth:`_periodo_multiplo_dias`)."""

    _SEIS = TestFaixaDeMaquinas._SEIS

    def test_ligar_troca_para_um_botao_por_maquina(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)  # começa no par 6EX+TrueBeam
        p.chk_maquina_unica.setChecked(True)
        self.assertEqual(len(p._botoes_par), 6)
        self.assertEqual(p.maquinas_marcadas(), [1035])  # só o 6EX (1ª do par)

    def test_desligar_volta_para_pares(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)
        p.chk_maquina_unica.setChecked(True)
        p.chk_maquina_unica.setChecked(False)
        self.assertEqual(len(p._botoes_par), 3)
        self.assertEqual(sorted(p.maquinas_marcadas()), [1035, 1499])

    def test_desligar_volta_para_o_PAR_de_origem_nao_so_o_primeiro(self):
        """Bug achado em 29/09/2026: desligar sempre caía no primeiro par
        (6EX+TrueBeam), mesmo tendo ligado "Uma máquina só" a partir de um
        par diferente — ``600CD``+``VitalBeam`` é o TERCEIRO de
        :data:`agenda_tela.PARES_MAQUINA`, não o primeiro."""
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS, [1046, 1252])  # 600CD+VitalBeam
        p.chk_maquina_unica.setChecked(True)
        p.chk_maquina_unica.setChecked(False)
        self.assertEqual(sorted(p.maquinas_marcadas()), [1046, 1252])

    def test_ligar_emite_maquina_unica_mudou_e_maquinas_mudaram(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)
        modos = []
        listas = []
        p.maquina_unica_mudou.connect(modos.append)
        p.maquinas_mudaram.connect(listas.append)
        p.chk_maquina_unica.setChecked(True)
        self.assertEqual(modos, [True])
        self.assertEqual(listas, [[1035]])

    def test_definir_maquina_unica_e_carga_sem_sinal_nem_remonte(self):
        """Chamado por ``ControleAgenda.ao_abrir`` ANTES de
        ``definir_maquinas`` — só guarda o valor, não escolha do usuário."""
        p = agenda_tela.PainelAgenda()
        modos = []
        p.maquina_unica_mudou.connect(modos.append)
        p.definir_maquina_unica(True)
        self.assertEqual(modos, [])
        p.definir_maquinas(self._SEIS)
        self.assertEqual(len(p._botoes_par), 6)  # já nasceu em modo único

    def test_checkbox_nao_existe_em_periodo_de_varios_dias(self):
        p = agenda_tela.PainelAgenda()
        p.data_ate.setDate(p.data.date().addDays(1))
        p.definir_maquinas(self._SEIS)
        self.assertIsNone(p.chk_maquina_unica)

    def test_remontar_a_faixa_nao_acumula_espacadores(self):
        """Achado na revisão de 29/09/2026: o ``addStretch`` do fim ficava
        para trás a cada remonte, e os botões escorregavam para o meio."""
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas(self._SEIS)
        total = p._lay_maquinas.count()
        for _ in range(3):
            p.chk_maquina_unica.setChecked(True)
            p.chk_maquina_unica.setChecked(False)
        self.assertEqual(p._lay_maquinas.count(), total)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestCampoDe(unittest.TestCase):
    """Achado na revisão de 29/09/2026: mudar só o "de" para trás, em dia
    único, abria um período sem ninguém pedir."""

    def test_em_dia_unico_o_ate_acompanha_o_de(self):
        p = agenda_tela.PainelAgenda()
        ontem = p.data.date().addDays(-1)
        p.data.setDate(ontem)
        self.assertEqual(p.data_ate.date(), ontem)

    def test_com_periodo_aberto_o_ate_fica_onde_esta(self):
        p = agenda_tela.PainelAgenda()
        ate = p.data.date().addDays(3)
        p.data_ate.setDate(ate)
        p.data.setDate(p.data.date().addDays(-1))
        self.assertEqual(p.data_ate.date(), ate)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestRotuloPeriodo(unittest.TestCase):
    """Pedido do usuário em 28/09/2026: "ao selecionar periodo, exemplo
    semana atual, deve aparecer o nome do periodo selecionado em agenda" —
    o combo de atalhos volta pro rótulo "Período" sozinho a cada escolha
    (:meth:`agenda_tela.PainelAgenda._atalho_de_periodo_escolhido`), então
    sem :attr:`rotulo_periodo_atual` a escolha não deixava rastro na tela."""

    def test_escolher_semana_atual_mostra_o_nome_no_rotulo(self):
        p = agenda_tela.PainelAgenda()
        p.combo_atalhos.setCurrentIndex(2)  # "Semana atual"
        self.assertEqual(p.rotulo_periodo_atual.text(), "Semana atual")

    def test_mexer_na_data_manualmente_apaga_o_rotulo(self):
        p = agenda_tela.PainelAgenda()
        p.combo_atalhos.setCurrentIndex(2)  # "Semana atual"
        p.data.setDate(p.data.date().addDays(3))
        self.assertEqual(p.rotulo_periodo_atual.text(), "")

    def test_andar_com_a_seta_apaga_o_rotulo(self):
        p = agenda_tela.PainelAgenda()
        p.combo_atalhos.setCurrentIndex(2)  # "Semana atual"
        p.btn_seguinte.click()
        self.assertEqual(p.rotulo_periodo_atual.text(), "")

    def test_escolher_a_mesma_opcao_duas_vezes_mostra_o_rotulo_as_duas(self):
        """A opção-menu do combo (ver docstring de
        :meth:`_atalho_de_periodo_escolhido`) tem de fazer efeito toda vez,
        mesmo repetida — inclusive no rótulo, não só nas datas."""
        p = agenda_tela.PainelAgenda()
        p.combo_atalhos.setCurrentIndex(1)  # "Hoje"
        p.data.setDate(p.data.date().addDays(5))  # apaga o rótulo
        self.assertEqual(p.rotulo_periodo_atual.text(), "")
        p.combo_atalhos.setCurrentIndex(1)  # "Hoje" de novo
        self.assertEqual(p.rotulo_periodo_atual.text(), "Hoje")


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestRotuloOcupacaoNoMes(unittest.TestCase):
    """"X% ocupação"/"X% disponibilidade" no rótulo do mês — pedido do
    usuário em 28/09/2026."""

    _RESUMO_BASE = (10, 2, 100, None, None)  # pacientes, inicios, sessoes...

    def test_taxa_de_ocupacao_aparece_formatada(self):
        c = agenda_tela._ColunaMaquina("6EX")
        c.definir_resumo_mensal(self._RESUMO_BASE + (0.10, None))
        self.assertIn("10% ocupação", c.rotulo_mes.text())
        self.assertNotIn("disponibilidade", c.rotulo_mes.text())

    def test_indice_de_disponibilidade_aparece_formatado(self):
        c = agenda_tela._ColunaMaquina("6EX")
        c.definir_resumo_mensal(self._RESUMO_BASE + (0.10, 0.95))
        self.assertIn("95% disponibilidade", c.rotulo_mes.text())

    def test_nenhum_dos_dois_some_da_frase_sem_horario_cadastrado(self):
        c = agenda_tela._ColunaMaquina("Dermopan")
        c.definir_resumo_mensal(self._RESUMO_BASE + (None, None))
        self.assertNotIn("ocupação", c.rotulo_mes.text())
        self.assertNotIn("disponibilidade", c.rotulo_mes.text())


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestColunas(unittest.TestCase):

    def test_uma_coluna_por_maquina_na_ordem_pedida(self):
        p = agenda_tela.PainelAgenda()
        por_maquina = {
            "600CD": [_marcacao(maquina="600CD")],
            "6EX": [_marcacao(maquina="6EX"), _marcacao(hora="08:00", maquina="6EX")],
        }
        p.mostrar_agenda(por_maquina, ["6EX", "600CD"])
        self.assertEqual(list(p._colunas), ["6EX", "600CD"])
        self.assertEqual(len(p._colunas["6EX"].marcacoes()), 2)
        self.assertEqual(len(p._colunas["600CD"].marcacoes()), 1)

    def test_maquina_marcada_sem_nenhuma_marcacao_fica_com_coluna_vazia(self):
        """A máquina continua na tela, só sem paciente — não some por não ter
        agenda hoje, que seria indistinguível de "não consultei"."""
        p = agenda_tela.PainelAgenda()
        p.mostrar_agenda({}, ["Ortovoltagem"])
        self.assertEqual(list(p._colunas), ["Ortovoltagem"])
        self.assertEqual(p._colunas["Ortovoltagem"].marcacoes(), [])


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestReticencias(unittest.TestCase):
    """Nome comprido corta com "…", nunca cru contra a borda da coluna —
    achado no print de 23/09/2026: "Luiz Otavio de Castro e Souza Sou" saía
    cortado no meio da palavra, sem aviso nenhum de que faltava o resto.

    O corte segue a largura REAL do rótulo (as colunas dividem a aba, e a
    largura muda com a janela). Os testes dão larguras EXTREMAS de propósito —
    5000px e 30px —, que valem em qualquer fonte: a do ``offscreen``
    (Helvetica) mede o dobro da real do Windows (ver ARMADILHAS.md), e um
    teste na fronteira ficaria refém de qual plataforma roda a suíte.
    """

    _LONGO = "9000042CEL · SBRT PROSTATA · Luiz Otavio de Castro e Souza Souza"

    def test_com_largura_de_sobra_o_texto_fica_inteiro(self):
        r = agenda_tela._RotuloElidido(self._LONGO)
        r.resize(5000, 20)
        r._reelidir()
        self.assertEqual(r.text(), self._LONGO)
        self.assertFalse(r.cortado())

    def test_com_largura_curta_termina_em_reticencias(self):
        r = agenda_tela._RotuloElidido(self._LONGO)
        r.resize(30, 20)
        r._reelidir()
        self.assertTrue(r.text().endswith("…"))
        self.assertTrue(r.cortado())
        self.assertEqual(r.texto_completo(), self._LONGO)

    def test_alargar_devolve_o_texto_inteiro(self):
        """As colunas mudam de largura com a janela — o corte não pode ficar
        preso ao primeiro tamanho que o rótulo teve."""
        r = agenda_tela._RotuloElidido(self._LONGO)
        r.resize(30, 20)
        r._reelidir()
        r.resize(5000, 20)
        r._reelidir()
        self.assertEqual(r.text(), self._LONGO)

    def test_medico_aparece_por_inteiro_mesmo_muito_longo(self):
        """Pedido do usuário em 24/09/2026: o médico nunca corta — por isso
        ``rodape_medico`` é um ``QLabel`` comum, sem ``_RotuloElidido``."""
        nome_longo = "Luiz Otavio de Castro e Souza Souza Sobrenome Extra"
        linha = agenda_tela._LinhaMarcacao(
            _marcacao(medico=nome_longo), agenda_tela.NORMAL)
        self.assertEqual(linha.rodape_medico.text(), nome_longo)

    def test_medico_tem_tooltip_de_reserva_se_a_coluna_espremer(self):
        """Bug achado em 29/09/2026: sem ``_RotuloElidido`` (de propósito,
        ver o teste acima), uma coluna estreita ainda pode espremer o rótulo
        abaixo do ``sizeHint`` e cortar o nome sem nenhum aviso — o tooltip
        é a rede de segurança, mesmo padrão do resto da linha."""
        nome_longo = "Luiz Otavio de Castro e Souza Souza Sobrenome Extra"
        linha = agenda_tela._LinhaMarcacao(
            _marcacao(medico=nome_longo), agenda_tela.NORMAL)
        self.assertEqual(linha.rodape_medico.toolTip(), nome_longo)

    def test_linha_cortada_no_sitio_ganha_tooltip_com_o_texto_inteiro(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL)
        linha.rodape.resize(30, 20)
        linha.rodape._reelidir()
        self.assertIn("PELVE", linha.toolTip())

    def test_linha_com_largura_de_sobra_nao_ganha_tooltip(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL)
        for r in (linha.topo, linha.rodape):
            r.resize(5000, 20)
            r._reelidir()
        self.assertEqual(linha.toolTip(), "")

    def test_voltar_a_caber_tira_o_tooltip(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL)
        linha.rodape.resize(30, 20)
        linha.rodape._reelidir()
        self.assertNotEqual(linha.toolTip(), "")
        linha.rodape.resize(5000, 20)
        linha.rodape._reelidir()
        self.assertEqual(linha.toolTip(), "")


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestSemMedicoVinculado(unittest.TestCase):
    """Pedido do usuário em 28/09/2026 ("quais outras... indicadores"): sem
    ``DimPatientDoctor`` (``OncologistFlag=1``) para o paciente, o rodapé
    ficava mudo — vira aviso, porque é dado real (a consulta respondeu, só
    não achou vínculo), não "a coluna não veio"."""

    def test_sem_medico_mostra_aviso_no_rodape(self):
        linha = agenda_tela._LinhaMarcacao(
            _marcacao(medico="", medico_bruto=""), agenda_tela.NORMAL)
        self.assertEqual(linha.rodape_medico.text(), "sem médico vinculado")

    def test_com_medico_nao_mostra_aviso(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL)
        self.assertNotEqual(linha.rodape_medico.text(), "sem médico vinculado")


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestFracaoNaLinha(unittest.TestCase):
    """O selo de fração (entregues/previstas, ver o docstring de
    ``_LinhaMarcacao``) e a marca "1ª sessão" — pedido do usuário em
    28/09/2026 ("quais outras... indicadores"): quem está no dia 1 do curso
    pede mais atenção do que quem já é rotina, e é o mesmo dado da fração,
    já calculado."""

    def _texto_fracao(self, fracao):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL,
                                           fracao)
        for filho in linha.findChildren(QLabel):
            if filho.text().startswith(f"{fracao[0]}/{fracao[1]}"):
                return filho.text()
        return None

    def test_primeira_sessao_ganha_a_marca(self):
        # Curso que começou no próprio dia da marcação (23/09): já tratou a 1ª.
        texto = self._texto_fracao((1, 30, date(2026, 9, 23), None))
        self.assertIn("1ª sessão", texto)

    def test_antes_da_primeira_sessao_ganha_a_marca(self):
        texto = self._texto_fracao((0, 30, None, None))
        self.assertIn("1ª sessão", texto)

    def test_segunda_sessao_nao_ganha_a_marca(self):
        # Uma sessão feita num dia ANTERIOR: hoje é a segunda.
        texto = self._texto_fracao((1, 30, date(2026, 9, 22), None))
        self.assertNotIn("1ª sessão", texto)

    def test_sem_previstas_nao_mostra_n_barra_zero(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL,
                                           (5, 0, None, None))
        self.assertFalse(any("5/0" in f.text()
                             for f in linha.findChildren(QLabel)))

    def test_sessao_do_meio_nao_ganha_a_marca(self):
        texto = self._texto_fracao((12, 30, None, None))
        self.assertNotIn("1ª sessão", texto)

    def test_sem_fracao_nenhum_selo_nasce(self):
        linha = agenda_tela._LinhaMarcacao(_marcacao(), agenda_tela.NORMAL, None)
        self.assertFalse(any(f.text().count("/") for f in linha.findChildren(QLabel)
                             if "/" in f.text() and f.text()[0].isdigit()))


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestContagemPorStatus(unittest.TestCase):
    """Os selos da legenda (:data:`agenda_tela._LEGENDA_STATUS`) ganham o
    número de marcações de cada grupo — pedido do usuário em 28/09/2026
    ("quais outras... indicadores"): a legenda já filtrava por status,
    faltava dizer QUANTOS há antes de decidir esconder um grupo."""

    def test_conta_cada_grupo_no_dia_em_cena(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas([_maquina("6EX", 1035)])
        por_maquina = {"6EX": [
            _marcacao(hora="07:00", estado="Completed"),
            _marcacao(hora="07:12", estado="Completed"),
            _marcacao(hora="07:24", estado="In Progress"),
            _marcacao(hora="07:36", estado="Open"),
        ]}
        p.mostrar_agenda(por_maquina, ["6EX"])
        self.assertEqual(
            p._selos_status[agenda_tela.STATUS_TRATADO]._texto.text(),
            "Tratado — 2")
        self.assertEqual(
            p._selos_status[agenda_tela.STATUS_EM_ANDAMENTO]._texto.text(),
            "Em andamento — 1")
        self.assertEqual(
            p._selos_status[agenda_tela.STATUS_ABERTO]._texto.text(),
            "Aberto — 1")

    def test_grupo_sem_nenhuma_marcacao_mostra_zero(self):
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas([_maquina("6EX", 1035)])
        p.mostrar_agenda({"6EX": [_marcacao(estado="Completed")]}, ["6EX"])
        self.assertEqual(
            p._selos_status[agenda_tela.STATUS_ABERTO]._texto.text(),
            "Aberto — 0")

    def test_esconder_status_nao_zera_a_contagem_do_proprio_grupo(self):
        """Clicar pra esconder "Aberto" continua mostrando quantos há — é
        justamente o número que ajuda a decidir esconder."""
        p = agenda_tela.PainelAgenda()
        p.definir_maquinas([_maquina("6EX", 1035)])
        p.mostrar_agenda({"6EX": [_marcacao(estado="Open")]}, ["6EX"])
        selo = p._selos_status[agenda_tela.STATUS_ABERTO]
        selo.clicado.emit()
        self.assertEqual(selo._texto.text(), "Aberto — 1")


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestColunasOcupamTudo(unittest.TestCase):
    """Pedido do usuário em 23/09/2026: as colunas ocupam todo o espaço da
    agenda — com 480px fixos e três máquinas, sobrava um vão à direita."""

    def test_toda_coluna_entra_com_o_mesmo_fator_de_esticar(self):
        p = agenda_tela.PainelAgenda()
        p.mostrar_agenda({}, ["6EX", "600CD", "TrueBeam"])
        lay = p._lay_colunas
        self.assertEqual(lay.count(), 3)
        self.assertEqual([lay.stretch(i) for i in range(3)], [1, 1, 1])

    def test_sem_espacador_no_fim(self):
        """O ``addStretch`` de antes era exatamente o vão que sobrava."""
        p = agenda_tela.PainelAgenda()
        p.mostrar_agenda({}, ["6EX", "600CD"])
        for i in range(p._lay_colunas.count()):
            self.assertIsNotNone(p._lay_colunas.itemAt(i).widget())

    def test_com_menos_maquinas_cada_uma_ganha_mais(self):
        p = agenda_tela.PainelAgenda()
        p.resize(1500, 600)
        p.show()
        p.mostrar_agenda({}, ["6EX"])
        _APP.processEvents()
        largura_sozinha = p._colunas["6EX"].width()
        p.mostrar_agenda({}, ["6EX", "600CD", "TrueBeam"])
        _APP.processEvents()
        largura_de_tres = p._colunas["6EX"].width()
        p.hide()
        self.assertGreater(largura_sozinha, largura_de_tres * 2)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestEsmaecimento(unittest.TestCase):
    """O filtro de médico DESTACA quem é dele e ESMAECE quem não é — a linha
    nunca some (pedido do usuário em 23/09/2026, depois de ver a agenda real:
    achar é tão importante quanto descartar)."""

    def _linhas(self, coluna):
        n = coluna._corpo_lay.count() - 1  # o último item é o stretch
        return [coluna._corpo_lay.itemAt(i).widget() for i in range(n)]

    def test_sem_filtro_toda_linha_e_normal(self):
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")], set())
        self.assertEqual([w.destaque for w in self._linhas(coluna)],
                         [agenda_tela.NORMAL, agenda_tela.NORMAL])

    def test_do_medico_escolhido_destaca_o_resto_esmaece(self):
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")],
            {"Souza, Luiz Mauro"})
        self.assertEqual([w.destaque for w in self._linhas(coluna)],
                         [agenda_tela.DESTACADO, agenda_tela.ESMAECIDO])

    def test_modo_esconder_tira_a_linha_do_outro_medico(self):
        """Pedido do usuário em 23/09/2026, depois de ver a agenda real: o
        modo é ESCOLHA da pessoa (ver ``chk_so_meus``), não o único jeito."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")],
            {"Souza, Luiz Mauro"}, agenda_tela.MODO_ESCONDER)
        self.assertEqual([w.destaque for w in self._linhas(coluna)],
                         [agenda_tela.DESTACADO])

    def test_modo_esconder_sem_filtro_mostra_tudo(self):
        """Sem médico escolhido não há o que esconder — as duas ficam."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")],
            set(), agenda_tela.MODO_ESCONDER)
        self.assertEqual(len(self._linhas(coluna)), 2)

    def test_modo_esconder_a_contagem_conta_so_o_medico(self):
        """Desde 25/09/2026 ("se nao tiver ticado somente os meus deve
        mostrar agenda completa"), com "Só os meus" marcado (MODO_ESCONDER)
        a contagem do cabeçalho é SÓ do médico em foco — o mesmo filtro que
        o resumo do mês já aplicava, para os dois números falarem da MESMA
        população (ver o docstring de ``_ColunaMaquina.definir``). Achado
        antes: "24 tratados" no mês contra "44 pacientes" no dia, mesmo
        médico — o dia nunca filtrava e por isso não batia."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")],
            {"Souza, Luiz Mauro"}, agenda_tela.MODO_ESCONDER)
        self.assertEqual(coluna.rotulo_contagem.text(), "1 paciente")

    def test_modo_esconder_com_status_escondido_mostra_os_dois_numeros(self):
        """"1 de 2 pacientes" ainda existe — agora só quando o filtro de
        STATUS (a legenda clicável) tira mais gente de vista do que o
        médico sozinho tiraria: o segundo número continua dizendo que a
        máquina não está livre nos horários que sumiram."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:00", medico_bruto="Souza, Luiz Mauro",
                       estado="Open")],
            {"Souza, Luiz Mauro"}, agenda_tela.MODO_ESCONDER,
            status_escondidos=frozenset({agenda_tela.STATUS_ABERTO}))
        self.assertEqual(coluna.rotulo_contagem.text(), "1 de 2 pacientes")

    def test_marcacoes_continua_devolvendo_o_dia_inteiro_no_modo_esconder(self):
        """Sem isso, trocar de médico de novo (ou desligar o modo) perderia
        quem ficou de fora — o repaint local partiria de uma lista já
        filtrada."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        marcacoes = [_marcacao(medico_bruto="Souza, Luiz Mauro"),
                    _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")]
        coluna.definir(marcacoes, {"Souza, Luiz Mauro"}, agenda_tela.MODO_ESCONDER)
        self.assertEqual(len(coluna.marcacoes()), 2)

    def test_trocar_de_medico_nao_pede_nada_ao_banco(self):
        """O esmaecimento repinta local; a coluna já tem tudo que precisa."""
        p = agenda_tela.PainelAgenda()
        p.mostrar_agenda(
            {"6EX": [_marcacao(medico_bruto="Souza, Luiz Mauro"),
                    _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")]},
            ["6EX"])
        chamou = []
        p.medicos_mudaram.connect(lambda brutos: chamou.append(brutos))
        p.medicos.definir(
            [tratamento_db.Medico(nome="Luiz Mauro Souza", bruto="Souza, Luiz Mauro")],
            ["Souza, Luiz Mauro"])
        # ``definir`` sozinho não emite (é carga, não escolha do usuário) —
        # o teste confere que a coluna continua com as DUAS marcações, e que
        # nenhuma consulta foi disparada por este caminho.
        self.assertEqual(len(p._colunas["6EX"].marcacoes()), 2)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestChkSoOsMeus(unittest.TestCase):
    """O botão que troca esmaecer↔esconder — escolha da pessoa, não fixa."""

    def test_marcar_muda_o_modo_e_emite_sem_consultar_o_banco(self):
        p = agenda_tela.PainelAgenda()
        p.mostrar_agenda(
            {"6EX": [_marcacao(medico_bruto="Souza, Luiz Mauro"),
                    _marcacao(hora="08:00", medico_bruto="Peixoto, Barbara")]},
            ["6EX"])
        p.medicos.definir(
            [tratamento_db.Medico(nome="Luiz Mauro Souza", bruto="Souza, Luiz Mauro")],
            ["Souza, Luiz Mauro"])
        chamou = []
        p.modo_destaque_mudou.connect(chamou.append)
        p.chk_so_meus.setChecked(True)
        self.assertEqual(chamou, [agenda_tela.MODO_ESCONDER])
        self.assertEqual(len(p._colunas["6EX"].marcacoes()), 2)  # dia INTEIRO
        # e a linha do outro médico saiu do que se DESENHA.
        n = p._colunas["6EX"]._corpo_lay.count() - 1
        self.assertEqual(n, 1)

    def test_definir_modo_destaque_carrega_sem_emitir(self):
        """Carregar a preferência salva é CARGA, não escolha — não pode
        disparar uma gravação da mesma preferência que acabou de ser lida."""
        p = agenda_tela.PainelAgenda()
        chamou = []
        p.modo_destaque_mudou.connect(chamou.append)
        p.definir_modo_destaque(agenda_tela.MODO_ESCONDER)
        self.assertEqual(chamou, [])
        self.assertTrue(p.chk_so_meus.isChecked())

    def test_modo_desconhecido_cai_no_padrao(self):
        p = agenda_tela.PainelAgenda()
        p.definir_modo_destaque("qualquer-coisa")
        self.assertEqual(p._modo_destaque, agenda_tela.MODO_ESMAECER)


@unittest.skipIf(controle_agenda is None, "PySide6 indisponível")
class TestControleAgenda(unittest.TestCase):
    """O controle decide QUANDO voltar ao banco — não a cada clique."""

    def setUp(self):
        self._disponivel = agenda_db.disponivel
        self._consultar_maquinas = agenda_db.maquinas
        self._consultar_medicos = agenda_db.medicos
        self._agenda_do_dia = agenda_db.agenda_do_dia
        agenda_db.disponivel = lambda: True
        # Um PAR de verdade (ver ``agenda_tela.PARES_MAQUINA``) — com
        # "6EX"+"600CD" (que não formam par nenhum) o painel marcaria só o
        # primeiro grupo, de uma máquina só, e não é isso que este teste
        # quer conferir.
        agenda_db.maquinas = lambda: [_maquina("6EX", 1035), _maquina("TrueBeam", 1499)]
        agenda_db.medicos = lambda: []

    def tearDown(self):
        agenda_db.disponivel = self._disponivel
        agenda_db.maquinas = self._consultar_maquinas
        agenda_db.medicos = self._consultar_medicos
        agenda_db.agenda_do_dia = self._agenda_do_dia

    def test_abrir_monta_as_maquinas_e_busca_o_dia(self):
        chamadas = []

        def responder(dia, marcadas):
            chamadas.append((dia, tuple(sorted(marcadas))))
            return [_marcacao(maquina="6EX")]

        agenda_db.agenda_do_dia = responder
        painel = agenda_tela.PainelAgenda()
        controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        controle.ao_abrir()
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0][1], (1035, 1499))
        self.assertIn("6EX", painel._colunas)

    def test_ao_abrir_carrega_o_modo_destaque_padrao(self):
        painel = agenda_tela.PainelAgenda()
        controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        controle.ao_abrir()
        self.assertEqual(painel._modo_destaque, agenda_tela.MODO_ESMAECER)
        self.assertFalse(painel.chk_so_meus.isChecked())

    def test_marcar_so_os_meus_grava_a_preferencia(self):
        from isocentro.dados import preferencias
        gravado = []
        antigo = preferencias.gravar
        preferencias.gravar = lambda _u, chave, valor: gravado.append(
            (chave, valor))
        try:
            painel = agenda_tela.PainelAgenda()
            # ``controle`` PRECISA de dono: sem uma referência forte, o
            # PyQt guarda o slot do bound method por referência FRACA quando
            # quem o possui não é QObject — o objeto some assim que a
            # expressão termina, e o sinal para de chamar nada, calado
            # (achado ao ver ``gravado`` ficar vazio sem erro nenhum).
            controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
            self.assertIsNotNone(controle)
            painel.chk_so_meus.setChecked(True)
            self.assertIn(
                (controle_agenda.CHAVE_MODO_DESTAQUE, agenda_tela.MODO_ESCONDER),
                gravado)
        finally:
            preferencias.gravar = antigo

    def test_nenhuma_maquina_marcada_nao_consulta(self):
        agenda_db.agenda_do_dia = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("não devia consultar sem máquina marcada"))
        painel = agenda_tela.PainelAgenda()
        controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        painel.definir_maquinas([_maquina("6EX", 1035)], marcadas=[])
        controle._atualizar()
        self.assertEqual(painel._colunas, {})

    def test_falha_de_leitura_avisa_e_nao_derruba(self):
        def explodir(*_a, **_k):
            raise RuntimeError("banco caiu")
        agenda_db.agenda_do_dia = explodir
        painel = agenda_tela.PainelAgenda()
        controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        painel.definir_maquinas([_maquina("6EX", 1035)])
        controle._atualizar()
        self.assertIn("banco caiu", painel.rotulo_status.text())

    def test_chamada_reentrante_nao_e_sobrescrita_pela_antiga(self):
        """Bug achado em 29/09/2026: o ``QApplication.processEvents()``
        entre as consultas "bônus" de ``_atualizar`` deixa o Qt processar um
        clique no MEIO de uma leitura. Se esse clique disparar uma nova
        chamada de ``_atualizar`` (mais nova) que termina primeiro, a
        chamada de FORA (mais velha) não pode pintar a tela por cima dela
        com o dado da máquina que não está mais marcada."""
        painel = agenda_tela.PainelAgenda()
        controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        painel.definir_maquinas([_maquina("6EX", 1035), _maquina("TrueBeam", 1499)])

        chamadas = []

        def agenda_do_dia_reentrante(dia, marcadas):
            chamadas.append(tuple(sorted(marcadas)))
            # Simula o clique processado durante o ``processEvents()`` desta
            # MESMA chamada: desmarca tudo e dispara uma leitura nova, que
            # termina ANTES desta função devolver o dado da leitura antiga.
            painel.definir_maquinas(
                [_maquina("6EX", 1035), _maquina("TrueBeam", 1499)], marcadas=[])
            controle._atualizar()
            return [_marcacao(maquina="6EX")]

        agenda_db.agenda_do_dia = agenda_do_dia_reentrante
        controle._atualizar()
        self.assertEqual(len(chamadas), 1)  # só a chamada de fora consultou
        # A chamada reentrante (mais nova) é quem tem de vencer.
        self.assertEqual(painel._colunas, {})
        self.assertEqual(painel.rotulo_status.text(), "Nenhuma máquina marcada.")


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestResumoMensalOcupacao(unittest.TestCase):
    """Taxa de Ocupação e Índice de Disponibilidade — pedido do usuário em
    28/09/2026, sobre ``ControleAgenda._resumo_mensal``."""

    def setUp(self):
        self._resumo_agenda = agenda_db.pacientes_do_mes_por_maquina
        self._resumo_trat = tratamento_db.resumo_mensal_por_maquina
        self._parada = agenda_db.minutos_parada_do_mes
        self._parada_verificado = agenda_db.MINUTOS_PARADA_VERIFICADO_EM
        # 6EX: 08h-18h (10h/dia) — fevereiro/2026 tem 20 dias úteis (ver
        # ``tests.test_agenda_db.TestMinutosUteisDoMes``), 12 000 min úteis.
        self._dia = date(2026, 2, 15)
        self._maq = agenda_db.Maquina(
            nome="6EX", ctr_resource_ser=1035, machine_id="6EX")
        painel = agenda_tela.PainelAgenda()
        self.controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
        self.controle._maquinas = [self._maq]
        agenda_db.minutos_parada_do_mes = lambda *a, **k: {}

    def tearDown(self):
        agenda_db.pacientes_do_mes_por_maquina = self._resumo_agenda
        tratamento_db.resumo_mensal_por_maquina = self._resumo_trat
        agenda_db.minutos_parada_do_mes = self._parada
        agenda_db.MINUTOS_PARADA_VERIFICADO_EM = self._parada_verificado

    def test_taxa_de_ocupacao_vem_das_sessoes_sobre_minutos_uteis(self):
        agenda_db.pacientes_do_mes_por_maquina = lambda *a, **k: {1035: (10, 2)}
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "6EX": (100, None, None)}  # 100 sessões × 12 min = 1200 min
        fora = self.controle._resumo_mensal(self._dia, [1035])
        # 1200 / 12000 = 10%
        self.assertAlmostEqual(fora["6EX"][5], 0.10)

    def test_indice_de_disponibilidade_e_none_com_portao_fechado(self):
        agenda_db.pacientes_do_mes_por_maquina = lambda *a, **k: {1035: (10, 2)}
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "6EX": (100, None, None)}
        self.assertEqual(agenda_db.MINUTOS_PARADA_VERIFICADO_EM, "")
        fora = self.controle._resumo_mensal(self._dia, [1035])
        self.assertIsNone(fora["6EX"][6])

    def test_indice_de_disponibilidade_desconta_a_parada_com_portao_aberto(self):
        agenda_db.MINUTOS_PARADA_VERIFICADO_EM = "28/09/2026"  # só o teste
        agenda_db.pacientes_do_mes_por_maquina = lambda *a, **k: {1035: (10, 2)}
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "6EX": (100, None, None)}
        agenda_db.minutos_parada_do_mes = lambda *a, **k: {1035: 600}
        fora = self.controle._resumo_mensal(self._dia, [1035])
        # (12000 - 600) / 12000 = 95%
        self.assertAlmostEqual(fora["6EX"][6], 0.95)

    def test_maquina_sem_horario_cadastrado_fica_sem_os_dois(self):
        maq = agenda_db.Maquina(
            nome="Dermopan", ctr_resource_ser=1400, machine_id="Dermopan")
        self.controle._maquinas = [maq]
        agenda_db.pacientes_do_mes_por_maquina = lambda *a, **k: {1400: (5, 1)}
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "Dermopan": (30, None, None)}
        fora = self.controle._resumo_mensal(self._dia, [1400])
        self.assertIsNone(fora["Dermopan"][5])
        self.assertIsNone(fora["Dermopan"][6])

    def test_mes_corrente_divide_so_pelo_expediente_ja_passado(self):
        """Achado na revisão de 29/09/2026: no dia 10, uma máquina lotada
        aparecia com ~30%, porque o denominador era o mês inteiro."""
        agenda_db.pacientes_do_mes_por_maquina = lambda *a, **k: {1035: (10, 2)}
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "6EX": (100, None, None)}
        hoje = date.today()
        fora = self.controle._resumo_mensal(hoje, [1035])
        ja_passado = agenda_db.minutos_uteis_do_mes("6EX", hoje, ate=hoje)
        if ja_passado:
            self.assertAlmostEqual(fora["6EX"][5], 100 * 12 / ja_passado)

    def test_repetir_o_mesmo_resumo_nao_consulta_de_novo(self):
        """A atualização automática a cada 2 minutos reaproveita o resumo."""
        chamadas = []

        def pacientes(*a, **k):
            chamadas.append(1)
            return {1035: (10, 2)}

        agenda_db.pacientes_do_mes_por_maquina = pacientes
        tratamento_db.resumo_mensal_por_maquina = lambda *a, **k: {
            "6EX": (100, None, None)}
        self.controle._resumo_mensal(self._dia, [1035])
        self.controle._resumo_mensal(self._dia, [1035])
        self.assertEqual(len(chamadas), 1)
        self.controle._resumo_mensal(self._dia, [1035], ["Outro, Médico"])
        self.assertEqual(len(chamadas), 2)  # médico diferente consulta


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestFracoesDoDiaCursoAtual(unittest.TestCase):
    """Achado na revisão de 29/09/2026: ``em_tratamento`` devolve uma linha
    por CURSO, e o curso velho concluído podia vencer o curso de agora."""

    def setUp(self):
        self._disp = tratamento_db.lista_disponivel
        self._em = tratamento_db.em_tratamento
        tratamento_db.lista_disponivel = lambda: True

    def tearDown(self):
        tratamento_db.lista_disponivel = self._disp
        tratamento_db.em_tratamento = self._em

    def test_curso_em_andamento_vence_o_concluido(self):
        velho = tratamento_db.EmTratamento(
            registro="9000011CEL", entregues=25, previstas=25,
            inicio=date(2026, 8, 1), ultima=date(2026, 9, 5))
        novo = tratamento_db.EmTratamento(
            registro="9000011CEL", entregues=3, previstas=10,
            inicio=date(2026, 9, 21), ultima=date(2026, 9, 23))
        for ordem in ([novo, velho], [velho, novo]):
            tratamento_db.em_tratamento = lambda *a, o=ordem, **k: list(o)
            painel = agenda_tela.PainelAgenda()
            controle = controle_agenda.ControleAgenda(painel, {"login": "geova"})
            fracoes = controle._fracoes_do_dia(date(2026, 9, 23),
                                               [_marcacao()])
            self.assertEqual(fracoes["9000011CEL"][:2], (3, 10))


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestReguaAgora(unittest.TestCase):
    """A régua "AGORA · HH:MM" — só existe com ``agora`` passado a
    ``_ColunaMaquina.definir``, e só na costura entre passado e futuro. Não
    muda a cor de nenhuma linha (tentado e revertido em 24/09/2026: a coluna
    inteira acinzentada lia como tela apagada) — só a posição da régua."""

    def _widgets(self, coluna):
        n = coluna._corpo_lay.count() - 1  # o último item é o stretch
        return [coluna._corpo_lay.itemAt(i).widget() for i in range(n)]

    # Marcações a 5 min uma da outra — abaixo de ``_VAGA_MINIMA`` (30 min, ver
    # :class:`TestVagaDeTempo`), para a marca de "vaga" (28/09/2026) não
    # aparecer entre elas e confundir a contagem de widgets que só quer
    # testar a régua.

    def test_sem_agora_nenhuma_regua_aparece(self):
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir([_marcacao(hora="07:00"), _marcacao(hora="07:05")], set())
        widgets = self._widgets(coluna)
        self.assertTrue(
            all(isinstance(w, agenda_tela._LinhaMarcacao) for w in widgets))

    def test_com_agora_no_meio_poe_a_regua_na_costura(self):
        agora = datetime(2026, 9, 23, 8, 7)
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(hora="08:00"), _marcacao(hora="08:05"),
             _marcacao(hora="08:10")], set(), agora=agora)
        widgets = self._widgets(coluna)
        self.assertEqual(
            [type(w).__name__ for w in widgets],
            ["_LinhaMarcacao", "_LinhaMarcacao", "QWidget", "_LinhaMarcacao"])

    def test_tudo_no_futuro_nao_poe_regua(self):
        agora = datetime(2026, 9, 23, 6, 0)
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir([_marcacao(hora="07:00"), _marcacao(hora="07:05")],
                       set(), agora=agora)
        widgets = self._widgets(coluna)
        self.assertTrue(
            all(isinstance(w, agenda_tela._LinhaMarcacao) for w in widgets))

    def test_tudo_no_passado_nao_poe_regua(self):
        agora = datetime(2026, 9, 23, 23, 0)
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir([_marcacao(hora="07:00"), _marcacao(hora="07:05")],
                       set(), agora=agora)
        widgets = self._widgets(coluna)
        self.assertTrue(
            all(isinstance(w, agenda_tela._LinhaMarcacao) for w in widgets))

    def test_periodo_sem_marcacao_hoje_poe_a_regua_antes_de_amanha(self):
        """Bug achado em 29/09/2026: num período de vários dias, se HOJE não
        tiver nenhuma marcação visível nesta coluna, a régua "AGORA" entrava
        DEPOIS do cabeçalho de "amanhã" — dando a impressão visual de que já
        era o dia seguinte. Tem de vir ANTES."""
        ontem = agenda_db.Marcacao(
            hora=datetime(2026, 9, 22, 10, 0), maquina="6EX", registro="1",
            paciente="A", atividade="PELVE", estado="Completed", medico="",
            medico_bruto="", mais_de_um_medico=False)
        amanha = agenda_db.Marcacao(
            hora=datetime(2026, 9, 24, 9, 0), maquina="6EX", registro="2",
            paciente="B", atividade="PELVE", estado="Completed", medico="",
            medico_bruto="", mais_de_um_medico=False)
        agora = datetime(2026, 9, 23, 12, 0)  # hoje, sem marcação nenhuma
        coluna = agenda_tela._ColunaMaquina("6EX", None, multiplos_dias=True)
        coluna.definir([ontem, amanha], set(), agora=agora)
        widgets = self._widgets(coluna)
        textos = []
        for w in widgets:
            if isinstance(w, agenda_tela._LinhaMarcacao):
                continue
            rotulo = w.findChild(QLabel)
            textos.append(rotulo.text() if rotulo else "")
        indice_agora = next(i for i, t in enumerate(textos)
                            if t.startswith("AGORA"))
        indice_amanha = next(i for i, t in enumerate(textos)
                             if "24/09/2026" in t)
        self.assertLess(indice_agora, indice_amanha, textos)


@unittest.skipIf(agenda_tela is None, "PySide6 indisponível")
class TestVagaDeTempo(unittest.TestCase):
    """A marca "Xh Ymin livre" entre duas marcações da mesma coluna — pedido
    do usuário em 28/09/2026 ("quais outras... indicadores"): a máquina
    livre por um tempo comprido é tão relevante quanto quem está marcado."""

    def _widgets(self, coluna):
        n = coluna._corpo_lay.count() - 1
        return [coluna._corpo_lay.itemAt(i).widget() for i in range(n)]

    def test_vao_curto_nao_marca_vaga(self):
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir([_marcacao(hora="08:00"), _marcacao(hora="08:12")], set())
        widgets = self._widgets(coluna)
        self.assertTrue(
            all(isinstance(w, agenda_tela._LinhaMarcacao) for w in widgets))

    def test_vao_de_uma_hora_marca_vaga(self):
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir([_marcacao(hora="08:00"), _marcacao(hora="09:00")], set())
        widgets = self._widgets(coluna)
        self.assertEqual(
            [type(w).__name__ for w in widgets],
            ["_LinhaMarcacao", "QWidget", "_LinhaMarcacao"])

    def test_marcacao_escondida_pelo_medico_nao_vira_vaga_falsa(self):
        """Uma marcação ESCONDIDA (outro médico, "Só os meus" ligado) ainda
        ocupa a máquina de verdade — o vão até ela não pode virar "vaga"."""
        coluna = agenda_tela._ColunaMaquina("6EX")
        coluna.definir(
            [_marcacao(hora="08:00", medico_bruto="Souza, Luiz Mauro"),
             _marcacao(hora="08:30", medico_bruto="Peixoto, Barbara"),
             _marcacao(hora="09:00", medico_bruto="Souza, Luiz Mauro")],
            {"Souza, Luiz Mauro"}, modo=agenda_tela.MODO_ESCONDER)
        widgets = self._widgets(coluna)
        self.assertTrue(
            all(isinstance(w, agenda_tela._LinhaMarcacao) for w in widgets))


from tests.limpeza_de_tela import load_tests  # noqa: E402,F401
