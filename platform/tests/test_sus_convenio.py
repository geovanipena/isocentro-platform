"""O convênio do sistema responde por "é SUS?", e o popup só pergunta o resto.

O que quebrava no uso: a cada ficha do TrueBeam o programa parava para perguntar
"Este é um paciente SUS?" e pedir um Cartão SUS de quinze dígitos — um número que
o sistema já tem, e que a pessoa redigitava com o paciente esperando. Digitação
de quinze dígitos é erro esperando acontecer, e o número sai IMPRESSO na folha de
Registro de Tratamento.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isola o JSON do cadastro: ``coletar_sus`` grava nele ao decidir.
os.environ["ISOCENTRO_SUS_DIR"] = tempfile.mkdtemp()

from isocentro.dados import cadastro_sus as cs
from isocentro.interface import portao_ficha
from isocentro.interface.caso import Caso


class TestSusDoConvenio(unittest.TestCase):
    """A leitura do texto de convênio, que é onde mora a decisão."""

    def test_sus_com_carteirinha_e_o_cartao(self):
        self.assertEqual(cs.sus_do_convenio("SUS - 700000000000005"),
                         (True, "700000000000005"))

    def test_convenio_em_branco_e_nao_deu_para_saber(self):
        """``None`` não é "não é SUS" — é o sinal de perguntar."""
        self.assertEqual(cs.sus_do_convenio(""), (None, ""))
        self.assertEqual(cs.sus_do_convenio("   "), (None, ""))

    def test_outro_plano_nao_e_sus(self):
        self.assertEqual(cs.sus_do_convenio("UNIMED - 12345"), (False, ""))

    def test_sus_sem_numero_sabe_o_que_falta(self):
        self.assertEqual(cs.sus_do_convenio("SUS"), (True, ""))

    def test_nome_repetido_no_lugar_do_numero_nao_e_cartao(self):
        """O banco repete o nome do convênio quando não há carteirinha.

        É o mesmo caso que fazia a capa sair "Fusex - Fusex" (ver ``capa_db``).
        Aqui, "SUS - SUS" tem de virar "é SUS, falta o número".
        """
        self.assertEqual(cs.sus_do_convenio("SUS - SUS"), (True, ""))

    def test_numero_curto_nao_passa_por_cartao(self):
        """Cartão Nacional de Saúde tem quinze dígitos; seis não é um cartão."""
        self.assertEqual(cs.sus_do_convenio("SUS - 700000"), (True, ""))

    def test_susep_nao_e_sus(self):
        """Compara por palavra: ``"SUS" in nome`` casaria SUSEP e SUSPENSO."""
        self.assertEqual(cs.sus_do_convenio("SUSEP - 700000000000005"),
                         (False, ""))

    def test_sus_com_sufixo_ainda_e_sus(self):
        self.assertEqual(cs.sus_do_convenio("SUS/AIH - 700000000000005"),
                         (True, "700000000000005"))

    def test_numero_com_separadores_vira_digitos(self):
        self.assertEqual(cs.sus_do_convenio("SUS - 700 0000 0000 0013"),
                         (True, "700000000000013"))

    def test_quinze_digitos_que_nao_sao_cartao_nao_vao_para_o_papel(self):
        """O número do banco sai de um COALESCE de três colunas, e a última é o
        número do PLANO — o mesmo para todo paciente daquele convênio.

        Com quinze dígitos ele passaria por cartão e a folha de Registro de
        Tratamento sairia com o MESMO número para todos, sem perguntar a
        ninguém. O dígito verificador do CNS separa os dois casos.
        """
        self.assertEqual(cs.sus_do_convenio("SUS - 123456789012345"), (True, ""))

    def test_o_que_o_cartao_precisa_ter(self):
        self.assertTrue(cs.cartao_sus_valido("700000000000005"))   # provisório
        self.assertTrue(cs.cartao_sus_valido("123456789010000"))   # definitivo
        # Começo fora de 1, 2, 7, 8 e 9 não é CNS, mesmo fechando a conta.
        self.assertFalse(cs.cartao_sus_valido("300000000000000"))
        self.assertFalse(cs.cartao_sus_valido("70000000000000"))   # 14 dígitos
        self.assertFalse(cs.cartao_sus_valido(""))


class _Status:
    """A linha de status da janela, só para guardar o que foi anunciado."""

    def __init__(self):
        self.recados = []

    def showMessage(self, texto, ms=0):
        self.recados.append(texto)


class _Janela:
    """A ``JanelaPrincipal`` reduzida ao que o portão do SUS lê e grava dela.

    Montar a janela de verdade para isto custaria uma tela inteira por teste, e
    o que se testa aqui é a DECISÃO — quem é perguntado e quem não é.
    """

    def __init__(self):
        self.caso = Caso()
        self.status = _Status()
        self.alertas = 0             # quantas vezes o alerta de SUS sem número saiu


class _Portao(portao_ficha.PortaoDaFicha):
    """O ``PortaoDaFicha`` DE VERDADE, com as três portas para fora trocadas.

    Era uma classe falsa que emprestava os métodos da janela, um por um
    (``_coletar_sus = gui.JanelaPrincipal._coletar_sus``). Até 16/09/2026 (R-06,
    corte 4): herdando, o que se testa é o objeto que a janela usa, e método
    novo no fluxo do SUS entra no teste sem ninguém lembrar de emprestá-lo.

    Trocados só o banco (``sus_pelo_convenio``), a máquina e o popup. O
    ``alertar_sus_sem_numero`` é o de verdade: a memória de "já alertei este
    paciente" mora nele, e um dublê que contasse chamadas testaria o dublê.
    Quem é substituído é só o ``ui.alertar``, que abriria janela — ver o
    ``setUpModule`` deste arquivo.
    """

    def __init__(self, convenio=(None, "", "", ""), resposta=None,
                 elegivel=True):
        super().__init__(_Janela())
        self._convenio = convenio
        self._resposta = resposta
        self._elegivel = elegivel
        self.perguntas = []          # (sus_atual, numero_atual) de cada popup

    def maquina_sus_elegivel(self):
        return self._elegivel

    def sus_pelo_convenio(self, registro):
        return self._convenio

    def perguntar_sus(self, sus_atual=False, numero_atual=""):
        self.perguntas.append((sus_atual, numero_atual))
        return self._resposta

    def perguntar_sus_cadastrado(self, prev):
        # Não existe mais (04/09/2026): fica aqui como ARMADILHA. Se alguém
        # reintroduzir a pergunta, ela aparece em ``perguntas`` e os testes
        # abaixo reprovam — em vez de a barreira voltar em silêncio.
        self.perguntas.append(("cadastrado", prev))
        return "alterar"


# O ``ui.alertar`` abriria janela de verdade em teste. Trocado para o módulo
# inteiro, e não caso a caso: são 22 chamadas de ``coletar_sus`` aqui, e um
# ``with`` em cada uma seria ruído sem leitor.
#
# Ele recebe a janela como PAI (``ui.alertar(self.janela, …)``), e é por isso
# que o contador consegue ser por janela sem que ninguém o passe.
_ALERTAR_REAL = None


def setUpModule():
    global _ALERTAR_REAL
    _ALERTAR_REAL = portao_ficha.ui.alertar

    def _contar(pai, titulo, texto, detalhe="", tecnico=""):
        pai.alertas = getattr(pai, "alertas", 0) + 1

    portao_ficha.ui.alertar = _contar


def tearDownModule():
    # Devolver, nunca ``del``: ``modulo.f = falsa`` grava no ``__dict__`` do
    # módulo, e o ``del`` depois some com a ORIGINAL para o resto do processo.
    if _ALERTAR_REAL is not None:
        portao_ficha.ui.alertar = _ALERTAR_REAL


def _dados(registro="R-SUS-1"):
    return {"pac_nome": "Fulano de Tal", "pac_nascimento": "01/02/1990",
            "pac_registro": registro}


class TestColetarSus(unittest.TestCase):
    def setUp(self):
        p = cs.caminho()
        if p.exists():
            p.unlink()

    def test_convenio_sus_com_numero_nao_pergunta_nada(self):
        j = _Portao(convenio=(True, "700000000000005", "banco (variandw)",
                              "SUS - 700000000000005"))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [])
        self.assertTrue(d["pac_sus"])
        self.assertEqual(d["numero_sus"], "700000000000005")

    def test_convenio_de_outro_plano_nao_pergunta_e_nao_e_sus(self):
        """Sem as folhas de Registro de Tratamento — e sem popup nenhum."""
        j = _Portao(convenio=(False, "", "banco (variandw)", "UNIMED"))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [])
        self.assertFalse(d["pac_sus"])
        self.assertEqual(d["numero_sus"], "")

    def test_decisao_calada_nao_existe(self):
        """Toda decisão tomada sem perguntar é ANUNCIADA na linha de status.

        E o recado diz o convênio e a porta de correção: quem vir "UNIMED" num
        paciente do SUS precisa saber para onde ir (a aba Capa).
        """
        j = _Portao(convenio=(False, "", "banco (variandw)", "UNIMED"))
        j.coletar_sus(_dados())
        self.assertEqual(len(j.janela.status.recados), 1)
        recado = j.janela.status.recados[0]
        self.assertIn("UNIMED", recado)
        self.assertIn("banco", recado)
        self.assertIn("Capa", recado)

    def test_sus_sem_numero_ALERTA_e_nao_pergunta(self):
        """O servidor já respondeu o que decide a ficha: o paciente é SUS.

        O número que falta é dado de CADASTRO dele, e pedi-lo a cada ficha é
        exigir quinze dígitos de cor de quem está montando um paciente.
        Decidido em 04/09/2026: sai direto do servidor, e o que falta vira
        alerta.
        """
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"),
                    resposta=(True, "700000000000021"))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [], "voltou a perguntar")
        self.assertEqual(j.janela.alertas, 1)
        self.assertTrue(d["pac_sus"])
        self.assertEqual(d["numero_sus"], "")

    def test_sus_sem_numero_nao_passa_pelo_manter_ou_alterar(self):
        """O cadastro guardado pode ser de quando o paciente NÃO era SUS.

        Perguntar "manter o cadastro?" depois de o banco dizer que é SUS é
        oferecer desfazer o que acabou de ser respondido.
        """
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", False, "")
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"),
                    resposta=(True, "800000000000028"))
        j.coletar_sus(_dados())
        self.assertEqual(j.perguntas, [])
        self.assertEqual(j.janela.alertas, 1, "o cadastro de NÃO SUS não tem número "
                                       "a aproveitar — tinha de alertar")

    def test_sus_sem_numero_aproveita_o_numero_guardado(self):
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", True,
                     "800000000000001")
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"),
                    resposta=(True, "800000000000001"))
        d = _dados()
        j.coletar_sus(d)
        # Nem pergunta nem alerta: o número guardado foi digitado e conferido
        # por uma pessoa, e o servidor não o devolver agora não o torna falso.
        self.assertEqual(j.perguntas, [])
        self.assertEqual(j.janela.alertas, 0)
        self.assertEqual(d["numero_sus"], "800000000000001")
        self.assertIn("cadastro deste paciente", " ".join(j.janela.status.recados))

    def test_sem_resposta_do_sistema_pergunta_como_sempre(self):
        """Banco desligado ou paciente que ele não conhece: nada mudou."""
        j = _Portao(convenio=(None, "", "", ""), resposta=(True, "800000000000036"))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [(False, "")])
        self.assertEqual(j.janela.status.recados, [])
        self.assertEqual(d["numero_sus"], "800000000000036")

    def test_cancelar_o_popup_aborta_a_ficha(self):
        j = _Portao(convenio=(None, "", "", ""), resposta=None)
        self.assertFalse(j.coletar_sus(_dados()))

    def test_maquina_sem_fluxo_sus_nem_consulta(self):
        j = _Portao(convenio=(True, "700000000000005", "banco", "SUS"),
                    elegivel=False)
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertNotIn("pac_sus", d)
        self.assertEqual(j.perguntas, [])

    def test_nao_sus_nao_leva_numero_para_o_papel(self):
        """Responder "Não" com número digitado não pode imprimir o número."""
        j = _Portao(convenio=(None, "", "", ""),
                    resposta=(False, "700000000000005"))
        d = _dados()
        j.coletar_sus(d)
        self.assertFalse(d["pac_sus"])
        self.assertEqual(d["numero_sus"], "")
        self.assertEqual(cs.consultar("Fulano de Tal", "01/02/1990",
                                      "R-SUS-1")["numero_sus"], "")

    def test_nao_sus_do_banco_nao_apaga_o_cartao_ja_confirmado(self):
        """O cadastro local é a memória do que um HUMANO afirmou.

        Gravar o "não é SUS" do convênio por cima dela bastaria uma linha de
        payor desatualizada no banco para o número sumir da reserva — e, no dia
        em que o banco não respondesse, a reserva passaria a responder "não é
        SUS" com a autoridade de quem foi conferido.
        """
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", True,
                     "700000000000005")
        j = _Portao(convenio=(False, "", "banco (variandw)", "UNIMED"))
        d = _dados()
        j.coletar_sus(d)
        self.assertFalse(d["pac_sus"])          # esta ficha sai sem as folhas
        guardado = cs.consultar("Fulano de Tal", "01/02/1990", "R-SUS-1")
        self.assertTrue(guardado["pac_sus"])    # …e a memória continua lá
        self.assertEqual(guardado["numero_sus"], "700000000000005")

    def test_a_decisao_do_convenio_fica_no_cadastro_do_paciente(self):
        """Para a próxima ficha ter reserva se o banco estiver fora do ar."""
        j = _Portao(convenio=(True, "700000000000005", "banco (variandw)",
                              "SUS - 700000000000005"))
        j.coletar_sus(_dados())
        guardado = cs.consultar("Fulano de Tal", "01/02/1990", "R-SUS-1")
        self.assertTrue(guardado["pac_sus"])
        self.assertEqual(guardado["numero_sus"], "700000000000005")


class TestSusDoPaciente(unittest.TestCase):
    """A ordem das fontes: banco, e a correção manual por cima dele."""

    def setUp(self):
        from isocentro.banco import capa_db
        from isocentro.dados import correcoes
        self._capa_db = capa_db
        self._correcoes = correcoes
        # Guardar e devolver — ``del modulo.funcao`` some com a ORIGINAL para o
        # resto do processo (armadilha já paga neste repositório).
        self._orig = (capa_db.configurado, capa_db.cadastro_do_paciente,
                      correcoes.ler)

    def tearDown(self):
        (self._capa_db.configurado, self._capa_db.cadastro_do_paciente,
         self._correcoes.ler) = self._orig

    def _montar(self, convenio_banco=None, convenio_corrigido=None):
        from isocentro.banco import capa_dados
        self._capa_db.configurado = lambda: convenio_banco is not None
        self._capa_db.cadastro_do_paciente = (
            lambda reg: capa_dados.Cadastro(registro=reg,
                                            convenio=convenio_banco)
            if convenio_banco is not None else None)
        self._correcoes.ler = (
            lambda reg: {"convenio": convenio_corrigido}
            if convenio_corrigido else {})

    def test_do_banco(self):
        self._montar(convenio_banco="SUS - 700000000000005")
        e_sus, numero, origem, convenio = cs.sus_do_paciente("R1")
        self.assertTrue(e_sus)
        self.assertEqual(numero, "700000000000005")
        self.assertIn("banco", origem)
        self.assertEqual(convenio, "SUS - 700000000000005")

    def test_correcao_manual_tem_a_ultima_palavra(self):
        """A correção existe porque o cadastro erra — ver ``correcoes.py``."""
        self._montar(convenio_banco="UNIMED",
                     convenio_corrigido="SUS - 700000000000013")
        e_sus, numero, origem, _c = cs.sus_do_paciente("R1")
        self.assertTrue(e_sus)
        self.assertEqual(numero, "700000000000013")
        self.assertEqual(origem, cs.ORIGEM_CORRECAO)

    def test_banco_desligado_e_nao_deu_para_saber(self):
        """Sem banco, NADA decide sozinho — nem espelho nem relatório.

        Os dois são retrato de outro dia, e um convênio velho decidiria calado
        se a folha de Registro de Tratamento entra ou não entra no maço.
        """
        self._montar(convenio_banco=None)
        self.assertEqual(cs.sus_do_paciente("R1"), (None, "", "", ""))

    def test_sem_registro_nem_consulta(self):
        self._montar(convenio_banco="SUS - 700000000000005")
        self.assertEqual(cs.sus_do_paciente(""), (None, "", "", ""))


class TestCadastroGuardadoEAnunciado(unittest.TestCase):
    """A tela "Manter o cadastro / Alterar" saiu — 04/09/2026.

    Ela só abria quando o BANCO NÃO RESPONDIA: com resposta, o convênio decide
    a ficha e ninguém é perguntado. Ou seja, a pergunta chegava justamente na
    hora em que não havia nada de novo para decidir — só a memória do que uma
    pessoa já tinha afirmado sobre este paciente.

    No lugar dela vale a regra da reserva anunciada, que a capa já usa: o
    guardado vale, e a barra DIZ que foi ele.
    """

    def setUp(self):
        p = cs.caminho()
        if p.exists():
            p.unlink()

    def test_nao_pergunta_nada_quando_ha_cadastro(self):
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", True,
                     "700000000000021")
        j = _Portao(convenio=(None, "", "", ""))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [], "a barreira voltou")
        self.assertTrue(d["pac_sus"])
        self.assertEqual(d["numero_sus"], "700000000000021")

    def test_a_barra_diz_que_veio_do_cadastro_e_onde_corrigir(self):
        """Aviso sem saída é notícia ruim e mais nada: quem lê precisa saber
        ONDE muda."""
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", True,
                     "700000000000021")
        j = _Portao(convenio=(None, "", "", ""))
        j.coletar_sus(_dados())
        recado = " ".join(j.janela.status.recados)
        self.assertIn("700000000000021", recado)
        self.assertIn("cadastro anterior", recado)
        self.assertIn("não respondeu", recado)
        self.assertIn("aba Capa", recado)

    def test_cadastro_de_NAO_sus_tambem_vale_sem_perguntar(self):
        cs.registrar("Fulano de Tal", "01/02/1990", "R-SUS-1", False, "")
        j = _Portao(convenio=(None, "", "", ""))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [])
        self.assertFalse(d["pac_sus"])
        self.assertIn("NÃO SUS", " ".join(j.janela.status.recados))

    def test_o_numero_da_SESSAO_nao_vira_cadastro_deste_paciente(self):
        """Achado na revisão de 04/09/2026.

        ``pref_num`` é o número lembrado da SESSÃO — do último paciente para
        quem alguém digitou um. Aproveitá-lo aqui gravaria o Cartão SUS de uma
        pessoa no cadastro de outra, e a barra ainda diria que veio "do
        cadastro deste paciente". Só o cadastro DELE vale.
        """
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"))
        j.janela.caso.sus = {"pac_sus": True, "numero_sus": "900000000000099"}
        d = _dados(registro="R-OUTRO")
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(d["numero_sus"], "", "usou o número de outro paciente")
        self.assertEqual(j.janela.alertas, 1)

    def test_o_alerta_sai_UMA_vez_por_paciente(self):
        """Achado na segunda revisão de 04/09/2026.

        O ``coletar_sus`` roda dentro da prévia automática, refeita a cada
        carga, a cada volta à Fichinha, a cada edição e a cada impressão. Sem
        memória, o modal voltaria em todas — e nada no fluxo o encerraria,
        porque um alerta, ao contrário da pergunta antiga, não grava nada.
        """
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"))
        d = _dados()
        j.coletar_sus(d)
        j.coletar_sus(d)
        j.coletar_sus(d)
        self.assertEqual(j.janela.alertas, 1, "o modal voltaria a cada prévia")

    def test_paciente_DIFERENTE_alerta_de_novo(self):
        """A memória é por paciente, não um interruptor: o segundo paciente sem
        número não pode herdar o silêncio do primeiro."""
        j = _Portao(convenio=(True, "", "banco (variandw)", "SUS"))
        j.coletar_sus(_dados(registro="R-UM"))
        j.coletar_sus(_dados(registro="R-DOIS"))
        self.assertEqual(j.janela.alertas, 2)

    def test_sem_cadastro_nenhum_a_pergunta_continua(self):
        """Tirar a barreira não é deixar de perguntar o que ninguém respondeu:
        paciente novo, com o banco calado, continua sendo perguntado."""
        j = _Portao(convenio=(None, "", "", ""),
                    resposta=(True, "800000000000036"))
        d = _dados()
        self.assertTrue(j.coletar_sus(d))
        self.assertEqual(j.perguntas, [(False, "")])
        self.assertEqual(d["numero_sus"], "800000000000036")


if __name__ == "__main__":
    unittest.main()
