"""A ferramenta que gera a ficha de um caso real (``tools/caso.py``).

Só a lógica PRÓPRIA dela: achar os casos e resolver o nome. Carregar um caso de
verdade leva de um a três minutos — é o que a ferramenta faz quando alguém a
chama, não o que a suíte deve refazer a cada rodada.

O que ela produz foi conferido à mão em 27/08/2026, nos dois fabricantes: TC8
(Varian, 2 planos, mama + FSC, 40,05 Gy/15 fr) e Elekta (Monaco, 5 planos,
Synergy01) — os dois geraram ficha completa, com dose, frações, SSD e
deslocamento no papel.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import caso as ferramenta  # noqa: E402


class TestAcharOsCasos(unittest.TestCase):

    def setUp(self):
        if not ferramenta.CASOS.is_dir():
            self.skipTest("TCs_Teste não está nesta estação")

    def test_a_pasta_do_banco_nao_e_um_caso(self):
        """``banco de dados`` é apoio do data warehouse, não um paciente.

        Sem esta exclusão ela aparecia na lista de casos e alguém tentaria
        gerar a ficha de uma pasta que não tem DICOM nenhum.
        """
        nomes = [p.name for p in ferramenta._casos_disponiveis()]
        self.assertNotIn("banco de dados", nomes)
        self.assertTrue(nomes, "não achei caso nenhum em TCs_Teste")

    def test_so_pasta_entra_na_lista(self):
        """Arquivo solto na raiz de TCs_Teste não é caso."""
        for p in ferramenta._casos_disponiveis():
            self.assertTrue(p.is_dir(), f"{p.name} não é pasta")

    def test_resolver_aceita_o_nome_em_qualquer_caixa(self):
        """Quem digita o caso na pressa escreve ``tc8``, não ``TC8``."""
        disponiveis = ferramenta._casos_disponiveis()
        alvo = next((p for p in disponiveis if p.name == "TC8"), None)
        if alvo is None:
            self.skipTest("TC8 não está nesta estação")
        self.assertEqual(ferramenta._resolver("TC8"), alvo)
        self.assertEqual(ferramenta._resolver("tc8"), alvo)
        self.assertEqual(ferramenta._resolver("Tc8"), alvo)

    def test_resolver_aceita_caminho_de_pasta(self):
        """Serve para conferir um caso que ainda não está em TCs_Teste."""
        achado = ferramenta._resolver(str(RAIZ / "tools"))
        self.assertIsNotNone(achado)
        self.assertEqual(Path(achado).name, "tools")

    def test_caso_que_nao_existe_devolve_None(self):
        """E aí o ``main`` lista os que existem, em vez de estourar."""
        self.assertIsNone(ferramenta._resolver("TC_QUE_NAO_EXISTE"))

    def test_a_contagem_ve_o_que_o_worker_ve(self):
        """Contar só ``.dcm`` esconde o caso que veio empacotado.

        O ``_CarregarTudo`` varre ``.dcm``, ``.zip`` E ``.rar`` — parte do
        acervo chega em pacote. A primeira versão da listagem contava apenas
        os ``.dcm`` e mostrava um número menor que o real: no Elekta, 1462 em
        vez de 1463; no TC6, 548 em vez de 549. Um caso inteiro dentro de um
        ``.rar`` apareceria como "0 arquivos" e ninguém tentaria gerá-lo.
        """
        for pasta in ferramenta._casos_disponiveis():
            so_dcm = sum(1 for _ in pasta.rglob("*.dcm"))
            self.assertGreaterEqual(
                ferramenta._quantos_arquivos(pasta), so_dcm,
                f"{pasta.name}: a contagem ficou ABAIXO do número de .dcm")

    def test_pasta_sem_dicom_conta_zero(self):
        """``Posicionamento`` guarda notas, não paciente — e a lista diz isso.

        Sem esta contagem, gerar a ficha dela montava a janela, varria a pasta
        e só então falhava com "Nada carregado", depois de um minuto de espera
        que não explicava nada.
        """
        notas = ferramenta.CASOS / "Posicionamento"
        if not notas.is_dir():
            self.skipTest("a pasta Posicionamento não está nesta estação")
        self.assertEqual(ferramenta._quantos_arquivos(notas), 0)


class TestOFluxoEODoPrograma(unittest.TestCase):
    """A ficha tem de sair pelo caminho por onde sai a da sala.

    Se a ferramenta remontasse os planos por conta própria, conferiria uma
    ficha que ninguém imprime — e a conferência não valeria nada. Estes testes
    leem o código porque rodar o fluxo carregaria um caso inteiro.
    """

    def test_usa_o_worker_do_programa(self):
        fonte = (RAIZ / "tools" / "caso.py").read_text(encoding="utf-8")
        self.assertIn("from isocentro.interface.carregadores import _CarregarTudo",
                      fonte,
                      "a ferramenta tem de usar o MESMO worker do botão "
                      "'Abrir pasta', não uma leitura própria")
        self.assertIn("janela.controle_ficha.montar_planos_pdf()", fonte,
                      "a montagem dos planos tem de ser a do programa")

    def test_nao_chama_o_carregar_pasta_que_pergunta(self):
        """``_carregar_pasta`` abre diálogos, e aqui não há quem responda.

        Ele confirma troca de paciente e pergunta reabrir-ou-nova. Num terminal
        isso trava a ferramenta esperando um clique que não vem.
        """
        fonte = (RAIZ / "tools" / "caso.py").read_text(encoding="utf-8")
        codigo = "\n".join(l for l in fonte.splitlines()
                           if not l.strip().startswith("#"))
        self.assertNotIn("janela._carregar_pasta(", codigo)
        self.assertNotIn("_abrir_agendamento_pendente", codigo)


class TestPerguntaDeDoseAlta(unittest.TestCase):
    """O modal que pendurava a ferramenta em todo caso de hipofracionamento.

    ``_plano_carregado`` — slot que a ferramenta reaproveita — abre
    ``perguntar_doses_altas`` acima de 600 cGy/fração. Offscreen esse modal não
    aparece e ninguém o fecha; o ``exec_()`` dele roda um laço aninhado, e nem a
    rede de 300 s salva, porque ela derruba o laço de FORA. TC6, TC7, TC9 e
    TC11 ficavam pendurados para sempre — justamente os casos que a régua do
    papel precisava conferir depois da mudança de ordem dos campos.
    """

    def setUp(self):
        from isocentro.interface import formulario
        self.formulario = formulario
        self.original = formulario.PainelFormulario.perguntar_doses_altas
        self.ditos: list = []

    def tearDown(self):
        # GUARDA E DEVOLVE — nunca ``del``: gravar por cima e apagar depois some
        # com a função original para o resto do processo.
        self.formulario.PainelFormulario.perguntar_doses_altas = self.original

    class _Aba:
        def __init__(self, dose, nfr, frac="", rotulo="P", prescrito=False):
            self._rotulo = rotulo
            self.rx_dose_fracao = TestPerguntaDeDoseAlta._Valor(dose)
            self.rx_fracoes = TestPerguntaDeDoseAlta._Valor(nfr)
            self.rx_fracionamento = TestPerguntaDeDoseAlta._Combo(frac)
            # Veio da prescrição aprovada? Então não se pergunta de novo.
            self._frac_prescrito = prescrito

    class _Valor:
        def __init__(self, v):
            self._v = v

        def value(self):
            return self._v

    class _Combo:
        def __init__(self, texto=""):
            self._t = texto

        def currentText(self):
            return self._t

        def setCurrentText(self, t):
            self._t = t

    class _Form:
        def __init__(self, abas):
            self._abas = abas
            self.abas = self

        def count(self):
            return len(self._abas)

        def widget(self, i):
            return self._abas[i]

    def _rodar(self, abas):
        ferramenta._responder_dose_alta(self.ditos.append)
        form = self._Form(abas)
        self.formulario.PainelFormulario.perguntar_doses_altas(form)
        return form

    def test_dose_alta_e_respondida_com_o_padrao_do_popup(self):
        aba = self._Aba(9.0, 3, rotulo="1_sPULMAO_E")
        self._rodar([aba])
        self.assertEqual(aba.rx_fracionamento.currentText(), "Dias alter.")

    def test_e_o_que_foi_respondido_sai_dito(self):
        """Ficha montada a partir de uma escolha que ninguém fez tem de
        anunciar a escolha — senão a conferência valida um palpite."""
        self._rodar([self._Aba(9.0, 3, rotulo="1_sPULMAO_E")])
        self.assertEqual(len(self.ditos), 1)
        self.assertIn("1_sPULMAO_E", self.ditos[0])
        self.assertIn("Dias alter.", self.ditos[0])
        self.assertIn("ninguém foi perguntado", self.ditos[0])

    def test_dose_normal_nao_responde_nada(self):
        aba = self._Aba(2.0, 25, frac="1x/dia")
        self._rodar([aba])
        self.assertEqual(aba.rx_fracionamento.currentText(), "1x/dia")
        self.assertEqual(self.ditos, [])

    def test_com_mais_de_um_plano_todos_entram(self):
        """É o que o popup faz: com dois planos ele lista os dois, porque o dia
        de início interliga um no outro."""
        alto = self._Aba(9.0, 3, rotulo="alto")
        normal = self._Aba(2.0, 25, frac="1x/dia", rotulo="normal")
        self._rodar([alto, normal])
        self.assertEqual(alto.rx_fracionamento.currentText(), "Dias alter.")
        self.assertEqual(len(self.ditos), 2)


if __name__ == "__main__":
    unittest.main()


class TestFracionamentoPrescritoNaoEPerguntado(unittest.TestCase):
    """O que a prescrição aprovada já diz não volta como pergunta.

    O pop-up de dose alta existia porque o fracionamento era digitado à mão. Com
    o ritmo vindo do ARIA, reabrir a escolha convida a trocar o que o
    radioterapeuta assinou — e, nos casos automáticos (``tools/caso.py``),
    ressuscita o modal que pendurava a ferramenta.
    """

    def setUp(self):
        from isocentro.interface import formulario
        self.formulario = formulario
        self.original = formulario.PainelFormulario.perguntar_doses_altas

    def tearDown(self):
        self.formulario.PainelFormulario.perguntar_doses_altas = self.original

    def test_aba_com_fracionamento_prescrito_nao_abre_o_popup(self):
        aba = TestPerguntaDeDoseAlta._Aba(9.0, 3, frac="Dias alter.",
                                          prescrito=True)
        form = TestPerguntaDeDoseAlta._Form([aba])
        # Sem nenhum plano "alto" a responder, o método volta ANTES de montar
        # o diálogo — offscreen, montá-lo penduraria a suíte.
        self.formulario.PainelFormulario.perguntar_doses_altas(form)
        self.assertEqual(aba.rx_fracionamento.currentText(), "Dias alter.")


class TestFracionamentoVemDaPrescricao(unittest.TestCase):
    """O ritmo do tratamento é prescrito e assinado; digitá-lo de novo em cada
    ficha é uma chance por ficha de divergir do que o radioterapeuta aprovou.

    Chama o método DESMONTADO da classe, com o dublê de abas: instanciar o
    painel subiria o Qt para responder uma pergunta que é de lógica.
    """

    def setUp(self):
        from isocentro.interface import formulario
        from isocentro.banco import tratamento_db
        self.formulario = formulario
        self.tratamento_db = tratamento_db
        self.original = tratamento_db.fracionamento_prescrito

    def tearDown(self):
        # GUARDA E DEVOLVE — nunca ``del``.
        self.tratamento_db.fracionamento_prescrito = self.original

    def _responder(self, resposta):
        self.tratamento_db.fracionamento_prescrito = (
            lambda registro, curso="": resposta)

    def _aplicar(self, abas, registro="9000001CEL"):
        form = TestPerguntaDeDoseAlta._Form(abas)
        return self.formulario.PainelFormulario.aplicar_fracionamento_prescrito(
            form, registro)

    def test_preenche_a_aba_vazia_e_marca_a_origem(self):
        self._responder({"fracionamento": "Dias alter.",
                         "frequencia": "Dias Alternados", "quantas": 1,
                         "escolhida": True})
        aba = TestPerguntaDeDoseAlta._Aba(9.0, 3)
        self.assertEqual(self._aplicar([aba]), "Dias Alternados")
        self.assertEqual(aba.rx_fracionamento.currentText(), "Dias alter.")
        self.assertTrue(aba._frac_prescrito)

    def test_nao_corrige_o_que_alguem_digitou(self):
        """A prescrição preenche o que está vazio. Sobrescrever uma escolha da
        pessoa a trocaria sem aviso, no meio da carga."""
        self._responder({"fracionamento": "1x dia", "frequencia": "once daily",
                         "quantas": 1, "escolhida": True})
        aba = TestPerguntaDeDoseAlta._Aba(2.0, 25, frac="2x sem.")
        self._aplicar([aba])
        self.assertEqual(aba.rx_fracionamento.currentText(), "2x sem.")
        self.assertFalse(aba._frac_prescrito)

    def test_duas_prescricoes_sem_casar_deixam_a_ficha_perguntar(self):
        """Num retratamento, herdar o ritmo do curso antigo poria na ficha um
        fracionamento que ninguém prescreveu para o que vai começar."""
        self._responder({"fracionamento": "", "frequencia": "", "quantas": 2,
                         "escolhida": False})
        aba = TestPerguntaDeDoseAlta._Aba(9.0, 3)
        self.assertEqual(self._aplicar([aba]), "")
        self.assertEqual(aba.rx_fracionamento.currentText(), "")
        self.assertFalse(aba._frac_prescrito)

    def test_sem_registro_nao_consulta_o_banco(self):
        """A carga sem paciente identificado não pode abrir consulta nenhuma."""
        def _proibido(registro, curso=""):
            raise AssertionError("consultou o banco sem registro")

        self.tratamento_db.fracionamento_prescrito = _proibido
        self.assertEqual(self._aplicar([TestPerguntaDeDoseAlta._Aba(2.0, 25)],
                                       registro="  "), "")

    def test_banco_que_levanta_nao_derruba_a_carga(self):
        """A ficha vive sem a prescrição: o campo fica vazio e alguém preenche."""
        def _explode(registro, curso=""):
            raise RuntimeError("sem conexão")

        self.tratamento_db.fracionamento_prescrito = _explode
        aba = TestPerguntaDeDoseAlta._Aba(2.0, 25)
        self.assertEqual(self._aplicar([aba]), "")
        self.assertFalse(aba._frac_prescrito)
