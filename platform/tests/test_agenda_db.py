"""A aba Agenda: o portão, o filtro de estado e a máquina que junta a marcação.

O que se testa aqui é sobretudo o que a consulta NÃO mostra — estado fechado,
paciente de teste, máquina não marcada — e a distinção ``None``/``[]`` que a
tela usa para separar "não consegui perguntar" de "perguntei e não há nada".

Rodar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import agenda_db  # noqa: E402
from isocentro.banco import capa_db as capa_db_modulo  # noqa: E402


class TestPortao(unittest.TestCase):
    """Sem mapeamento conferido, nada de agenda — nem uma máquina vazia."""

    def setUp(self):
        self._verificado = agenda_db.VERIFICADO_EM

    def tearDown(self):
        agenda_db.VERIFICADO_EM = self._verificado

    def test_aberto_com_a_data_da_conferencia(self):
        self.assertRegex(agenda_db.VERIFICADO_EM, r"^\d{2}/\d{2}/\d{4}$")

    def test_fechado_nao_consulta(self):
        agenda_db.VERIFICADO_EM = ""
        self.assertFalse(agenda_db.disponivel())
        self.assertEqual(agenda_db.maquinas(), [])
        self.assertIsNone(agenda_db.agenda_do_dia(date(2026, 9, 23), []))

    def test_motivo_distingue_banco_de_mapeamento(self):
        agenda_db.VERIFICADO_EM = ""
        motivo = agenda_db.motivo_indisponivel()
        self.assertTrue(motivo)
        esperado = "Serviço" if not capa_db_modulo.configurado() else "conferida"
        self.assertIn(esperado, motivo)


class TestMaquinas(unittest.TestCase):
    """A lista de checkboxes da tela."""

    def setUp(self):
        self._disponivel = agenda_db.disponivel
        self._consultar = capa_db_modulo._consultar
        agenda_db.disponivel = lambda: True

    def tearDown(self):
        agenda_db.disponivel = self._disponivel
        capa_db_modulo._consultar = self._consultar

    def test_monta_uma_maquina_por_linha(self):
        capa_db_modulo._consultar = lambda *_a, **_k: [
            ("6EX", "6EX", 1035), ("600CD", "600CD", 1046),
            ("TrueBeamSN1001", "VitalBeam", 1252)]
        fora = agenda_db.maquinas()
        self.assertEqual([m.nome for m in fora], ["6EX", "600CD", "VitalBeam"])
        self.assertEqual(fora[0].ctr_resource_ser, 1035)
        self.assertEqual(fora[2].machine_id, "TrueBeamSN1001")

    def test_linha_sem_nome_ou_sem_ctrResourceSer_nao_entra(self):
        """Campo sem fonte não vira máquina fantasma na lista de checkboxes."""
        capa_db_modulo._consultar = lambda *_a, **_k: [
            ("", "", 1035), ("6EX", "6EX", 0), ("600CD", "600CD", None),
            ("TrueBeamSN1001", "VitalBeam", 1252)]
        fora = agenda_db.maquinas()
        self.assertEqual([m.nome for m in fora], ["VitalBeam"])

    def test_a_consulta_exclui_as_maquinas_da_lista_negativa(self):
        """"Eclipse CAP" está Ativa e é Dispositivo de radiação no banco, mas
        não é máquina de verdade (pedido do usuário em 23/09/2026, depois de
        ver zero marcações no dia inteiro ao lado de quatro aceleradores
        cheios) — o filtro é no SQL, não descartado depois na tela."""
        capturado = {}

        def responder(sql, *params, **_k):
            capturado["sql"] = sql
            capturado["params"] = params
            return [("6EX", "6EX", 1035)]

        capa_db_modulo._consultar = responder
        agenda_db.maquinas()
        self.assertIn("rm.MachineId NOT IN (?)", capturado["sql"])
        self.assertEqual(capturado["params"], agenda_db.MAQUINAS_EXCLUIDAS)

    def test_o_nome_da_clinica_troca_o_do_ARIA(self):
        """"TB Universitario" é o que o ARIA guarda; "TrueBeam" é o que a
        clínica chama (pedido do usuário em 23/09/2026) — só esta máquina
        precisa de troca, as outras três já batem com ``MachineFullName``."""
        capa_db_modulo._consultar = lambda *_a, **_k: [
            ("TBuniverSN1002", "TB Universitario", 1499),
            ("GammaMed Plus", "Braquiterapia", 1014),
            ("Ortovoltagem", "Dermopan", 1346)]
        fora = agenda_db.maquinas()
        self.assertEqual([m.nome for m in fora],
                         ["TrueBeam", "Braquiterapia", "Dermopan"])

    def test_sem_nome_completo_cai_no_machine_id(self):
        capa_db_modulo._consultar = lambda *_a, **_k: [("6EX", "", 1035)]
        fora = agenda_db.maquinas()
        self.assertEqual(fora[0].nome, "6EX")

    def test_falha_de_leitura_devolve_lista_vazia(self):
        def explodir(*_a, **_k):
            raise capa_db_modulo.FalhaDeLeitura("derrubada")
        capa_db_modulo._consultar = explodir
        self.assertEqual(agenda_db.maquinas(), [])


class TestMedicos(unittest.TestCase):
    """O filtro de médico tem o PRÓPRIO portão — não o da Ficha Virtual.

    ``tratamento_db.LISTA_VERIFICADA_EM`` pode estar vazio (está, em
    23/09/2026) sem que isso deva esvaziar o seletor da Agenda: as duas telas
    não compartilham fonte de "posso mostrar médico", só a consulta.
    """

    def setUp(self):
        self._disponivel = agenda_db.disponivel
        agenda_db.disponivel = lambda: True

    def tearDown(self):
        agenda_db.disponivel = self._disponivel

    def test_portao_fechado_da_virtual_nao_esvazia_a_agenda(self):
        from isocentro.banco import tratamento_db
        antigo = tratamento_db.LISTA_VERIFICADA_EM
        antigo_metodo = tratamento_db._medicos_do_banco
        tratamento_db.LISTA_VERIFICADA_EM = ""
        tratamento_db._medicos_do_banco = lambda: [
            tratamento_db.Medico(nome="Luiz Mauro Souza", bruto="Souza, Luiz Mauro")]
        try:
            self.assertEqual(tratamento_db.medicos(), [],
                             "a Virtual continua fechada, é o portão dela")
            fora = agenda_db.medicos()
            self.assertEqual([m.nome for m in fora], ["Luiz Mauro Souza"])
        finally:
            tratamento_db.LISTA_VERIFICADA_EM = antigo
            tratamento_db._medicos_do_banco = antigo_metodo

    def test_fechado_devolve_lista_vazia(self):
        agenda_db.disponivel = lambda: False
        self.assertEqual(agenda_db.medicos(), [])


class TestAgendaDoDia(unittest.TestCase):
    """A marcação vira ``Marcacao``, e o SQL leva o filtro certo."""

    def setUp(self):
        self._disponivel = agenda_db.disponivel
        self._consultar = capa_db_modulo._consultar
        agenda_db.disponivel = lambda: True

    def tearDown(self):
        agenda_db.disponivel = self._disponivel
        capa_db_modulo._consultar = self._consultar

    def _linha(self, hora=None, maquina="6EX", maquina_completa="",
              registro="9000011CEL", paciente="Fulano, De Tal",
              atividade="PELVE", estado="Completed",
              medico="Souza, Luiz Mauro", quantos=1):
        return (hora or datetime(2026, 9, 23, 7, 36), maquina,
                maquina_completa, registro, paciente, atividade, estado,
                medico, quantos)

    def test_maquina_vazia_nao_consulta(self):
        """Nenhuma máquina marcada é o estado inicial da tela, não um erro —
        e não deve custar uma ida ao banco para responder lista vazia."""
        chamou = []
        capa_db_modulo._consultar = lambda *a, **k: chamou.append(a) or []
        self.assertEqual(agenda_db.agenda_do_dia(date(2026, 9, 23), []), [])
        self.assertEqual(chamou, [])

    def test_monta_a_marcacao_com_o_nome_desinvertido(self):
        """O banco guarda "Sobrenome, Nome"; a tela mostra o nome próprio —
        mesma regra do resto do app (``capa_dados.de_pessoa``)."""
        capa_db_modulo._consultar = lambda *_a, **_k: [self._linha()]
        fora = agenda_db.agenda_do_dia(date(2026, 9, 23), [1035])
        self.assertEqual(len(fora), 1)
        m = fora[0]
        self.assertEqual(m.maquina, "6EX")
        self.assertEqual(m.registro, "9000011CEL")
        self.assertEqual(m.paciente, "De Tal Fulano")
        self.assertEqual(m.atividade, "PELVE")
        self.assertEqual(m.estado, "Completed")
        self.assertEqual(m.medico, "Luiz Mauro Souza")
        self.assertFalse(m.mais_de_um_medico)

    def test_mais_de_um_medico_fica_marcado(self):
        capa_db_modulo._consultar = lambda *_a, **_k: [self._linha(quantos=2)]
        m = agenda_db.agenda_do_dia(date(2026, 9, 23), [1035])[0]
        self.assertTrue(m.mais_de_um_medico)

    def test_o_sql_leva_os_ctrResourceSer_marcados_e_os_estados_fora(self):
        """A máquina e o estado são filtro do SQL — não algo que a tela
        descarte depois de trazer o banco inteiro."""
        capturado = {}

        def responder(sql, *params, **_k):
            capturado["sql"] = sql
            capturado["params"] = params
            return []

        capa_db_modulo._consultar = responder
        agenda_db.agenda_do_dia(date(2026, 9, 23), [1035, 1046])
        sql = capturado["sql"]
        params = capturado["params"]
        self.assertIn("t.ctrResourceSer IN (?,?)", sql)
        self.assertIn("t.AppointmentStatus NOT IN (?,?,?)", sql)
        self.assertEqual(params[0], "2026-09-23")
        self.assertEqual(set(params[1:3]), {1035, 1046})
        self.assertEqual(set(params[3:]), set(agenda_db.ESTADOS_FORA))

    def test_aceita_maquina_objeto_ou_ctrResourceSer_cru(self):
        capturado = {}

        def responder(sql, *params, **_k):
            capturado["params"] = params
            return []

        capa_db_modulo._consultar = responder
        maq = agenda_db.Maquina(nome="6EX", ctr_resource_ser=1035)
        agenda_db.agenda_do_dia(date(2026, 9, 23), [maq, 1046])
        self.assertEqual(set(capturado["params"][1:3]), {1035, 1046})

    def test_falha_de_leitura_devolve_None_nao_lista_vazia(self):
        """"Não consegui perguntar" e "perguntei e não há nada" são respostas
        OPOSTAS para quem está na frente da tela."""
        def explodir(*_a, **_k):
            raise capa_db_modulo.FalhaDeLeitura("derrubada")
        capa_db_modulo._consultar = explodir
        self.assertIsNone(agenda_db.agenda_do_dia(date(2026, 9, 23), [1035]))


class TestEstadosFora(unittest.TestCase):
    """Lista NEGATIVA — um estado novo do ARIA tem de APARECER, não sumir."""

    def test_so_os_tres_cancelados_ficam_fora(self):
        self.assertEqual(agenda_db.ESTADOS_FORA,
                         ("Deleted", "Cancelled", "Cancelled - Patient No-Show"))

    def test_completed_nao_esta_fora(self):
        """A agenda do DIA mostra o dia inteiro — "Completed" de manhã é tão
        real quanto "Open" à tarde."""
        self.assertNotIn("Completed", agenda_db.ESTADOS_FORA)
        self.assertNotIn("Open", agenda_db.ESTADOS_FORA)
        self.assertNotIn("In Progress", agenda_db.ESTADOS_FORA)


class TestPorMaquina(unittest.TestCase):

    def test_agrupa_na_ordem_de_chegada(self):
        a = agenda_db.Marcacao(maquina="6EX", registro="1")
        b = agenda_db.Marcacao(maquina="600CD", registro="2")
        c = agenda_db.Marcacao(maquina="6EX", registro="3")
        agrupado = agenda_db.por_maquina([a, b, c])
        self.assertEqual(list(agrupado), ["6EX", "600CD"])
        self.assertEqual([m.registro for m in agrupado["6EX"]], ["1", "3"])

    def test_lista_vazia_devolve_dict_vazio(self):
        self.assertEqual(agenda_db.por_maquina([]), {})
        self.assertEqual(agenda_db.por_maquina(None), {})


class TestMinutosUteisDoMes(unittest.TestCase):
    """O denominador da Taxa de Ocupação e do Índice de Disponibilidade —
    pedido do usuário em 28/09/2026, com o horário de cada máquina."""

    def test_maquina_sem_horario_cadastrado_devolve_None(self):
        """Braquiterapia/Dermopan não foram citadas — nunca inventar
        expediente para elas."""
        self.assertIsNone(
            agenda_db.minutos_uteis_do_mes("Braquiterapia", date(2026, 2, 15)))

    def test_conta_so_dias_uteis_do_mes_pelo_horario_da_maquina(self):
        """Fevereiro/2026 tem 20 dias úteis (seg-sex) — conferido à parte,
        não pela mesma conta do código."""
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 15)),
            20 * 10 * 60)  # 8h-18h = 10h/dia
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("600CD", date(2026, 2, 1)),
            20 * 8 * 60)  # 8h-18h, menos o almoço 12h-14h = 8h/dia
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("VitalBeam", date(2026, 2, 28)),
            20 * 9 * 60)  # 7h-16h = 9h/dia
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("TrueBeam", date(2026, 2, 15)),
            20 * 13 * 60)  # 7h-20h = 13h/dia

    def test_referencia_em_qualquer_dia_do_mes_da_o_mesmo_total(self):
        """O mês INTEIRO (ver ``capa_dados.limites_do_mes``), não uma janela
        de 30 dias a partir de ``referencia``."""
        primeiro = agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 1))
        ultimo = agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 28))
        self.assertEqual(primeiro, ultimo)

    def test_ate_conta_so_os_dias_ja_passados(self):
        """Mês corrente: a ocupação divide pelo expediente que já passou.
        De 02/02 (seg) a 10/02/2026 (ter), inclusive, são 7 dias úteis."""
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 15),
                                           ate=date(2026, 2, 10)),
            7 * 10 * 60)

    def test_ate_depois_do_mes_nao_muda_o_total(self):
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 15),
                                           ate=date(2026, 9, 29)),
            20 * 10 * 60)

    def test_ate_antes_do_mes_da_zero(self):
        self.assertEqual(
            agenda_db.minutos_uteis_do_mes("6EX", date(2026, 2, 15),
                                           ate=date(2026, 1, 20)),
            0)


class TestMinutosParadaDoMes(unittest.TestCase):
    """Atrás do portão ``MINUTOS_PARADA_VERIFICADO_EM`` — ainda fechado
    (28/09/2026): as três hipóteses sobre "Atividade de Serviço"/"Parada
    Não Programada" (grafia, sem paciente, duração) não foram conferidas
    contra o ARIA real."""

    def setUp(self):
        self._disponivel = agenda_db.disponivel
        agenda_db.disponivel = lambda: True

    def tearDown(self):
        agenda_db.disponivel = self._disponivel

    def test_fechado_devolve_dict_vazio_mesmo_com_maquina_marcada(self):
        self.assertEqual(agenda_db.MINUTOS_PARADA_VERIFICADO_EM, "")
        self.assertEqual(
            agenda_db.minutos_parada_do_mes([1035], date(2026, 2, 15)), {})


if __name__ == "__main__":
    unittest.main()
