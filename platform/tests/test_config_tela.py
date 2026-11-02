"""Configurações → Serviço: os endereços num lugar só, e só para admin.

Os três endereços do serviço (banco, relatórios, simulações) ficavam como
botões na aba Capa, competindo com o trabalho de montar a folha e aparecendo
para quem não podia usá-los. Configuração se faz de propósito, uma vez.

O que estes testes fixam é o que dói se sair errado: um técnico apontando a
pasta e quebrando a capa de todo mundo, ou uma escolha de admin que vale só na
máquina em que foi digitada.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for _var in ("ISOCENTRO_SIMULACOES", "ISOCENTRO_INVENTARIO_DIR", "ISOCENTRO_NOTAS_DIR",
             "ISOCENTRO_USERS_DIR", "ISOCENTRO_CORRECOES"):
    os.environ.setdefault(_var, tempfile.mkdtemp(prefix="cfg_tela_"))

try:
    from unittest import mock

    from PySide6.QtWidgets import QApplication, QLabel, QTabWidget
    _APP = QApplication.instance() or QApplication([])

    from isocentro.dados import ambiente
    from isocentro.banco import capa_db
    from isocentro.dados import config_servico
    from isocentro.interface import gui
except Exception as exc:  # noqa: BLE001
    gui = None
    _MOTIVO = str(exc)


@unittest.skipIf(gui is None, "PySide6 indisponível")
class TestQuemVeOQue(unittest.TestCase):

    def _abas(self, papel: str) -> list:
        d = gui.DialogConfiguracoes({"usuario": "u", "papel": papel})
        abas = d.findChild(QTabWidget)
        try:
            # Sem abas nenhuma: quem não é admin recebe um recado, não um
            # diálogo vazio.
            if abas is None:
                return []
            return [abas.tabText(i) for i in range(abas.count())]
        finally:
            d.close()

    def test_admin_ve_o_servico(self):
        self.assertIn("Serviço", self._abas("admin"))

    def test_admin_ve_as_quatro(self):
        self.assertEqual(self._abas("admin"),
                         ["Serviço", "Usuários", "Equipe", "Máquinas"])

    def test_quem_nao_e_admin_nao_ve_nada(self):
        """Nem Máquinas: os aceleradores, suas energias e apelidos são cadastro
        que a ficha inteira usa. Quem monta ficha consome essa lista; quem a
        define é o admin — e o que parece inofensivo reaparece errado no papel
        de outra pessoa."""
        self.assertEqual(self._abas("tecnico"), [])


@unittest.skipIf(gui is None, "PySide6 indisponível")
class TestSalvar(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="cfg_servico_")
        self._env = os.environ.get("ISOCENTRO_CONFIG")
        os.environ["ISOCENTRO_CONFIG"] = self._dir
        self._srv = os.environ.pop(capa_db.ENV_SERVIDOR, None)
        # Os DOIS nomes: desde 09/09/2026 o ``capa_db`` lê pelo
        # ``ambiente.ler``, e tirar só o antigo deixaria o banco apontado numa
        # estação que já migrou para ``ISOCENTRO_DB_SERVIDOR``.
        self._srv_novo = os.environ.pop(
            ambiente.nome_novo(capa_db.ENV_SERVIDOR), None)
        self.d = gui.DialogConfiguracoes({"usuario": "geovani", "papel": "admin"})
        self.painel = self.d.findChild(QTabWidget).widget(0)

    def tearDown(self):
        self.d.close()
        if self._env is None:
            os.environ.pop("ISOCENTRO_CONFIG", None)
        else:
            os.environ["ISOCENTRO_CONFIG"] = self._env
        if self._srv is not None:
            os.environ[capa_db.ENV_SERVIDOR] = self._srv
        if self._srv_novo is not None:
            os.environ[ambiente.nome_novo(capa_db.ENV_SERVIDOR)] = self._srv_novo
        capa_db.esquecer()

    def test_variavel_da_estacao_avisa_no_campo_do_servidor(self):
        """A tela promete "mostra qual está valendo" — e no banco não mostrava.

        O admin salva SRVINSIGHT, lê "vale para todas as estações", e nesta
        máquina a capa continua nascendo de outro banco. Numa pasta isso
        atrasa alguém; aqui muda o dado que vai para o papel da sala, e o
        papel não diz de onde veio.
        """
        novo = ambiente.nome_novo(capa_db.ENV_SERVIDOR)
        os.environ[novo] = "SRV-DA-ESTACAO"
        capa_db.esquecer()
        try:
            self.painel._recarregar()
            texto = self.painel._campos[config_servico.DB_SERVIDOR][1].text()
        finally:
            os.environ.pop(novo, None)
            capa_db.esquecer()
        # O NOME que venceu, não o antigo genérico: com as duas definidas,
        # dizer "ISOCENTRO_*" mandaria o admin conferir a variável errada.
        self.assertIn("ISOCENTRO_DB_SERVIDOR", texto)
        self.assertIn("SRV-DA-ESTACAO", texto)

    def test_sem_variavel_o_campo_do_servidor_nao_alarma(self):
        """Aviso que aparece à toa é aviso que se aprende a ignorar."""
        self.painel._recarregar()
        texto = self.painel._campos[config_servico.DB_SERVIDOR][1].text()
        self.assertNotIn("⚠", texto)

    def _salvar(self):
        """Cala os pop-ups do salvamento — modal trava a suíte.

        Espia ``ui.avisar``/``ui.alertar``, e não mais ``QMessageBox`` (padrão
        de 25/08/2026). Ganho que veio de graça: são funções PYTHON, e
        ``mock.patch`` nelas é trivial — remendar um método estático de classe
        C++ do PyQt embaralhava a resolução de métodos da própria classe, e o
        ``exec_`` seguinte quebrava com um TypeError de ``unbound method``.
        """
        with mock.patch.object(gui.ui, "avisar"), \
             mock.patch.object(gui.ui, "alertar"):
            self.painel._salvar()

    def test_grava_na_configuracao_do_servico(self):
        """No arquivo compartilhado, não no QSettings: a escolha do admin tem
        de alcançar as outras estações."""
        self.painel._campos[config_servico.DB_SERVIDOR][0].setText("SRVINSIGHT")
        self._salvar()
        self.assertEqual(config_servico.valor(config_servico.DB_SERVIDOR),
                         "SRVINSIGHT")
        self.assertTrue(config_servico.caminho().exists())

    def test_guarda_quem_apontou(self):
        """Endereço de onde sai documento de paciente não é decisão anônima."""
        self.painel._campos[config_servico.DB_SERVIDOR][0].setText("SRVINSIGHT")
        self._salvar()
        quem, quando = config_servico.autoria(config_servico.DB_SERVIDOR)
        self.assertEqual(quem, "geovani")
        self.assertTrue(quando)

    def test_apagar_devolve_ao_padrao(self):
        """É como se desfaz um apontamento errado sem adivinhar o valor
        anterior — e como se desliga o banco, voltando aos relatórios."""
        self.painel._campos[config_servico.DB_SERVIDOR][0].setText("SRVINSIGHT")
        self._salvar()
        self.painel._campos[config_servico.DB_SERVIDOR][0].setText("")
        self._salvar()
        self.assertEqual(config_servico.valor(config_servico.DB_SERVIDOR), "")
        self.assertFalse(capa_db.configurado())

    def test_salvar_derruba_a_lista_de_pacientes_da_CAPA(self):
        """A lista da busca é lida uma vez por sessão; trocar o servidor sem
        derrubá-la deixa a busca oferecendo os pacientes do lugar antigo.

        Era ``hasattr(janela, "_pacientes_carregados")``. No corte 5 da R-06 o
        atributo foi para o ``ControleCapa``, e aquele ``hasattr`` passaria a
        dar falso sem erro nenhum — nenhum teste via essa porta."""
        from types import SimpleNamespace
        controle = SimpleNamespace(pacientes_carregados=True)
        janela = SimpleNamespace(controle_capa=controle)
        with mock.patch.object(self.painel, "window", return_value=janela):
            self._salvar()
        self.assertFalse(controle.pacientes_carregados)

    def test_todo_endereco_do_servico_esta_la(self):
        """A aba é a lista COMPLETA do que o admin aponta.

        Endereço que fica só em variável de ambiente é endereço que a TI
        configura máquina por máquina — e a estação esquecida não reclama, ela
        grava noutro lugar em silêncio. Foi o caso da pasta de exportação até
        04/09/2026.
        """
        self.assertEqual(
            set(self.painel._campos),
            {config_servico.DB_SERVIDOR, config_servico.PASTA_RELATORIOS,
             config_servico.RAIZ_SIMULACOES, config_servico.PASTA_EXPORTACAO,
             # As quatro da rede DICOM entraram em 14/09/2026: a varredura
             # passou a rodar por Tarefa Agendada, que usa outra conta do
             # Windows — e variável de usuário não atravessa conta.
             config_servico.DICOM_SERVIDOR, config_servico.DICOM_AE_REMOTO,
             config_servico.DICOM_AE_LOCAL, config_servico.DICOM_AE_DESTINO,
             # E a concentradora em 18/09/2026, consequência das quatro: com
             # a rede no arquivo, alguém tem de dizer QUAL máquina varre.
             config_servico.CONCENTRADORA})

    def test_o_campo_da_concentradora_diz_o_nome_desta_maquina(self):
        """É o que o admin precisa copiar quando está NA concentradora — e o
        IP, que é o que ele lembra, não casa com nome nenhum."""
        from isocentro.dominio import gatilho
        caixa = self.painel._campos[config_servico.CONCENTRADORA][0].parent()
        textos = " ".join(r.text() for r in caixa.findChildren(QLabel))
        self.assertIn(gatilho.nome_desta_maquina(), textos)

    def test_o_dialogo_cabe_em_tela_pequena(self):
        """Regressão de 04/09/2026, e ela era pior que o defeito que consertava.

        Dar altura aos rótulos que quebram linha (``MinimumExpanding``) empurrou
        a altura MÍNIMA do diálogo de 728 para 948 px, e ele deixou de encolher:
        em estação 1366x768 a faixa com "Salvar" caía fora da tela, sem rolagem
        e sem como redimensionar. O conteúdo passou a morar numa área de
        rolagem, onde as duas coisas valem juntas.

        O limite de 700 px não é redondo por acaso: é o que sobra de 768 depois
        da barra de tarefas e da moldura da janela.
        """
        self.assertLessEqual(
            self.d.minimumSizeHint().height(), 700,
            "o diálogo não cabe numa estação 1366x768")
        self.d.resize(900, 600)
        self.assertLessEqual(self.d.height(), 600,
                             "o diálogo se recusa a encolher")

    def test_a_variavel_da_estacao_aparece_na_tela(self):
        """Sem isto a tela mente por OMISSÃO.

        O admin aponta a pasta, lê "Salvo. Vale para todas as estações", e
        nesta máquina os planos continuam caindo noutro lugar — em silêncio,
        que é exatamente o modo de falhar que o campo existe para fechar.
        """
        from isocentro.dominio import gatilho
        antes = os.environ.get("ISOCENTRO_EXPORTACAO")
        os.environ["ISOCENTRO_EXPORTACAO"] = r"D:\local\exportacao"
        try:
            self.painel._recarregar()
            _campo, rotulo = self.painel._campos[
                config_servico.PASTA_EXPORTACAO]
            texto = rotulo.text()
            self.assertIn("ISOCENTRO_EXPORTACAO", texto)
            self.assertIn(r"D:\local\exportacao", texto)
            self.assertIn("estação", gatilho.origem_da_pasta())
        finally:
            if antes is None:
                os.environ.pop("ISOCENTRO_EXPORTACAO", None)
            else:
                os.environ["ISOCENTRO_EXPORTACAO"] = antes
        self.painel._recarregar()
        _campo, rotulo = self.painel._campos[config_servico.PASTA_EXPORTACAO]
        self.assertNotIn("⚠", rotulo.text())

    def test_a_variavel_da_estacao_avisa_tambem_no_campo_do_ARIA(self):
        """Mesmo aviso da pasta de exportação, e aqui ele custa mais.

        Na concentradora, o degrau que vale muda com a CONTA que roda: o admin
        preenche o servidor do ARIA, a estação dele continua usando a variável
        local, e a Tarefa Agendada (outra conta) usa o que está no arquivo. Sem
        o aviso, os dois lados parecem o mesmo.
        """
        antes = os.environ.get("ISOCENTRO_DICOM_SERVIDOR")
        os.environ["ISOCENTRO_DICOM_SERVIDOR"] = "srv-local:51404"
        try:
            self.painel._recarregar()
            _campo, rotulo = self.painel._campos[config_servico.DICOM_SERVIDOR]
            texto = rotulo.text()
            self.assertIn("ISOCENTRO_DICOM_SERVIDOR", texto)
            self.assertIn("srv-local:51404", texto)
        finally:
            if antes is None:
                os.environ.pop("ISOCENTRO_DICOM_SERVIDOR", None)
            else:
                os.environ["ISOCENTRO_DICOM_SERVIDOR"] = antes
        self.painel._recarregar()
        _campo, rotulo = self.painel._campos[config_servico.DICOM_SERVIDOR]
        self.assertNotIn("⚠", rotulo.text())

    def test_a_aba_cobre_as_CHAVES_do_config(self):
        """Chave nova no ``config_servico`` sem campo na tela é configuração
        que só se muda editando JSON à mão."""
        self.assertEqual(set(self.painel._campos) | {config_servico.DB_BANCO},
                         set(config_servico.CHAVES))


@unittest.skipIf(gui is None, "PySide6 indisponível")
class TestACapaNaoTemMaisOsBotoes(unittest.TestCase):
    """Eles saíram da tela de trabalho — e o recado tem de acompanhar."""

    def test_a_aba_capa_nao_expoe_pasta(self):
        from isocentro.interface import capa as capa_tela
        tela = capa_tela.PainelCapa()
        try:
            self.assertFalse(hasattr(tela, "btn_pasta_rel"))
            self.assertFalse(hasattr(tela, "btn_raiz_sim"))
        finally:
            tela.deleteLater()


# Esvazia ``estilo._ouvintes`` entre um teste e o seguinte. Sem isto, a lista
# cresce durante o arquivo inteiro e cada repintura percorre tudo o que já se
# acumulou — ver ``tests/limpeza_de_tela.py`` para os números.
from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
