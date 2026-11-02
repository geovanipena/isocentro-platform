"""O que a `tools/tela.py` não pode fazer com o ambiente e com a preferência.

Ela existe para conferir tela, e uma ferramenta de conferência que muda o que
veio conferir é pior que não ter ferramenta. Dois estragos possíveis, e os dois
já aconteceram por caminhos parecidos neste repositório:

  * mexer em ``QT_QPA_PLATFORM`` no import arrancaria o ``offscreen`` de baixo
    da suíte inteira — e o estrago apareceria em OUTRO arquivo de teste, na
    ordem alfabética do `discover`, como já aconteceu com o `test_capa_tela`
    antes do `test_capa`;
  * ``aplicar_modo`` GRAVA o modo nas preferências da estação, então capturar
    uma tela no claro deixaria o app do usuário no claro na próxima abertura.

Não monta janela nenhuma de propósito: o que se testa aqui são as decisões, e
elas são todas anteriores ao Qt.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for p in (RAIZ, RAIZ / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import tela as ferramenta  # noqa: E402


class TestOImportNaoMexeNoAmbiente(unittest.TestCase):
    """Importar a ferramenta não pode mudar a plataforma do Qt de ninguém."""

    def test_importar_nao_troca_a_plataforma(self):
        # Este arquivo já importou o módulo lá em cima. Se o import mexesse na
        # variável, a suíte inteira teria perdido o `offscreen` aqui — e os
        # testes de tela dos outros arquivos abririam janela de verdade.
        self.assertEqual(
            os.environ.get("QT_QPA_PLATFORM"), "offscreen",
            "importar tools/tela.py mexeu no QT_QPA_PLATFORM da suíte")

    def test_a_troca_mora_numa_funcao_chamada_pelo_main(self):
        fonte = (RAIZ / "tools" / "tela.py").read_text(encoding="utf-8")
        # A garantia que a ferramenta precisa é "antes do primeiro import de
        # PyQt do processo", e o `main` a cumpre. O que ela NÃO pode é cumpri-la
        # no topo do módulo, onde um import inocente a dispara.
        self.assertIn("escolher_plataforma()", fonte)
        topo = fonte.split("def escolher_plataforma")[0]
        self.assertNotIn('os.environ["QT_QPA_PLATFORM"]', topo,
                         "a troca de plataforma voltou para o topo do módulo")


class TestEscolherPlataforma(unittest.TestCase):
    """A plataforma tem de ser SOBRESCRITA, não completada."""

    def setUp(self):
        self.antes = os.environ.get("QT_QPA_PLATFORM")
        self.plataforma_real = ferramenta.sys.platform

    def tearDown(self):
        # Devolver o valor exato, inclusive a ausência dele: um `del` a mais
        # aqui deixaria os testes seguintes sem `offscreen`, que é justamente o
        # estrago que este arquivo existe para impedir.
        ferramenta.sys.platform = self.plataforma_real
        if self.antes is None:
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = self.antes

    def test_no_windows_sobrescreve_o_offscreen(self):
        """`setdefault` não serviria: a variável quase sempre JÁ existe.

        O `tools/caso.py` põe `offscreen` no momento em que é importado, e a
        tela.py o importa para carregar um caso. Um `setdefault` chegaria tarde
        e o PNG sairia com todos os rótulos vazios.
        """
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        ferramenta.sys.platform = "win32"
        self.assertEqual(ferramenta.escolher_plataforma(), "windows")
        self.assertEqual(os.environ["QT_QPA_PLATFORM"], "windows")

    def test_fora_do_windows_apaga_o_offscreen_em_vez_de_adivinhar(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        ferramenta.sys.platform = "linux"
        ferramenta.escolher_plataforma()
        self.assertNotIn("QT_QPA_PLATFORM", os.environ)


class TestAlvoECaminho(unittest.TestCase):
    def test_sem_dois_pontos_o_caminho_e_vazio(self):
        self.assertEqual(ferramenta._alvo_e_caminho("principal"),
                         ("principal", ""))

    def test_com_dois_pontos_separa(self):
        self.assertEqual(ferramenta._alvo_e_caminho("principal:form.pac_nome"),
                         ("principal", "form.pac_nome"))

    def test_espaco_em_volta_nao_conta(self):
        self.assertEqual(ferramenta._alvo_e_caminho(" principal : form "),
                         ("principal", "form"))


class TestDescer(unittest.TestCase):
    """Erro de digitação tem de virar mensagem, não traceback."""

    class _No:
        pass

    def setUp(self):
        self.raiz = self._No()
        self.raiz.form = self._No()
        self.raiz.form.pac_nome = "o widget"

    def test_desce_por_atributos_encadeados(self):
        self.assertEqual(ferramenta._descer(self.raiz, "form.pac_nome"),
                         "o widget")

    def test_atributo_que_nao_existe_devolve_None(self):
        # Devolver None (e não estourar) é o que deixa o `main` responder com a
        # lista do que EXISTE, que é o que resolve o erro de digitação na hora.
        self.assertIsNone(ferramenta._descer(self.raiz, "form.pac_nom"))

    def test_caminho_vazio_devolve_a_propria_raiz(self):
        self.assertIs(ferramenta._descer(self.raiz, ""), self.raiz)


class TestNaoMexeNaPreferenciaDaEstacao(unittest.TestCase):
    """O modo dia↔noite fica gravado; a ferramenta tem de devolvê-lo."""

    def setUp(self):
        self.fonte = (RAIZ / "tools" / "tela.py").read_text(encoding="utf-8")

    def test_le_o_modo_anterior_antes_de_trocar(self):
        # `aplicar_modo` devolve o modo NOVO, não o antigo — guardar o retorno
        # dela e "restaurar" com ele não restauraria nada. O anterior só pode
        # vir do `estilo.modo()`, perguntado antes da troca.
        self.assertIn("modo_antes = estilo.modo()", self.fonte)
        self.assertNotIn("modo_antes = gui.aplicar_modo", self.fonte)

    def test_a_devolucao_do_modo_esta_num_finally(self):
        # Num `finally` porque a captura falha de verdade: caso que não existe,
        # atributo errado, Qt em offscreen. Sair por qualquer um deles sem
        # devolver o modo deixaria a preferência do usuário mexida por um erro.
        depois_do_finally = self.fonte.rsplit("finally:", 1)[-1]
        self.assertIn("gui.aplicar_modo(modo_antes)", depois_do_finally)

    def test_recusa_o_offscreen_pela_plataforma_medida(self):
        # Pela MEDIDA (`platformName()`), não pela variável de ambiente: o Qt
        # escolhe a plataforma quando o QApplication nasce, e a variável pode
        # ter sido gravada tarde demais. É a diferença entre conferir e supor.
        self.assertIn('app.platformName() == "offscreen"', self.fonte)


if __name__ == "__main__":
    unittest.main()
