"""O ``connect`` sai da thread da interface: quem espera é o arranque, não a capa.

O ``connect`` custa até ``TEMPO_LIMITE_S`` (6 s) e roda onde for chamado. Como
a capa é montada na thread da interface, a PRIMEIRA capa de cada sessão pagava
esse tempo com a tela parada — numa estação fora do domínio, que nunca vai
conectar, eram ~8 s de janela congelada sem aviso nenhum.

O recuo de ``ESPERAS_APOS_FALHA_S`` já diminuía a frequência das travadas
seguintes, mas nunca a primeira. ``capa_db.aquecer()`` cobre justamente essa:
roda no arranque, durante o login, quando ninguém está olhando para a tela.

Estes testes fixam as três coisas que fazem o aquecimento valer a pena — que
ele não bloqueia quem o chama, que a falha do banco não vaza traceback para o
stderr, e que ele se cala quando não há servidor apontado.
"""
from __future__ import annotations

import ast
import os
import sys
import threading
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from isocentro.banco import capa_db  # noqa: E402
from tests import fontes  # noqa: E402


class TestAquecerNaoTrava(unittest.TestCase):
    """O aquecimento é para TIRAR a espera do caminho de quem trabalha."""

    def setUp(self):
        self.servidor_original = capa_db.servidor
        self.conexao_original = capa_db.conexao

    def tearDown(self):
        # Devolver, nunca ``del``: ``modulo.f = falsa`` grava no __dict__ do
        # módulo e o ``del`` sumiria com a ORIGINAL para o resto do processo.
        capa_db.servidor = self.servidor_original
        capa_db.conexao = self.conexao_original

    def test_aquecer_volta_na_hora_mesmo_com_o_banco_lento(self):
        """Se ``aquecer`` esperasse o connect, não teria resolvido nada.

        Este é o teste do defeito original: um connect de 6 s bloqueando quem
        chamou. Aqui o connect finge levar 2 s e o ``aquecer`` tem de voltar
        num piscar — senão a espera só teria mudado de lugar, do primeiro
        paciente para o arranque.
        """
        capa_db.servidor = lambda: "SRV-DE-MENTIRA"
        entrou = threading.Event()

        def _connect_lento():
            entrou.set()
            time.sleep(2)
            return None

        capa_db.conexao = _connect_lento

        inicio = time.monotonic()
        capa_db.aquecer()
        gasto = time.monotonic() - inicio

        self.assertLess(gasto, 0.5,
                        f"aquecer() segurou quem chamou por {gasto:.2f}s — o "
                        "connect tem de ficar na thread de fundo")
        self.assertTrue(entrou.wait(timeout=3),
                        "a thread de fundo nem chegou a tentar conectar")

    def test_o_banco_que_explode_nao_despeja_traceback(self):
        """A exceção da thread não pode escapar para o ``threading.excepthook``.

        Ela NÃO derruba o programa — a primeira versão deste teste dizia que
        sim, e estava errada: a rede de segurança do ``gui`` é
        ``sys.excepthook``, que não cobre thread nenhuma, e desde o 3.8 a
        thread tem hook próprio que só imprime e segue.

        O que ela faz é despejar um traceback cru no stderr. Neste projeto
        isso já mordeu: o ``tools/testar_reconexao.py`` precisa calar o logger
        do ``capa_db`` porque o despejo do driver saía encavalado, POR CIMA do
        recado que o relatório existia para mostrar. Um traceback do connect
        aparecendo no meio de uma conferência tem o mesmo efeito — e num
        executável sem console não aparece em lugar nenhum, que é pior.
        """
        capa_db.servidor = lambda: "SRV-DE-MENTIRA"
        tentou = threading.Event()

        def _connect_que_explode():
            tentou.set()
            raise RuntimeError("driver ODBC pegou fogo")

        capa_db.conexao = _connect_que_explode

        escapou = []
        hook_original = threading.excepthook
        threading.excepthook = escapou.append
        try:
            capa_db.aquecer()
            self.assertTrue(tentou.wait(timeout=3))
            for _ in range(30):   # a thread termina logo depois de levantar
                if not any(t.name == "capa_db.aquecer"
                           for t in threading.enumerate()):
                    break
                time.sleep(0.1)
        finally:
            threading.excepthook = hook_original

        self.assertEqual(
            [type(e.exc_value).__name__ for e in escapou], [],
            "a exceção escapou da thread e vai despejar traceback no stderr")

    def test_sem_servidor_apontado_nao_gasta_thread(self):
        """Estação que não usa banco não tem por que ganhar uma thread.

        ``configurado()`` falso significa que o módulo inteiro fica fora do
        caminho e a capa sai pelos relatórios — aquecer ali seria trabalho
        para jogar fora, e apareceria como thread órfã em toda estação que só
        usa CSV.
        """
        capa_db.servidor = lambda: ""
        chamou = threading.Event()
        capa_db.conexao = lambda: chamou.set()

        antes = threading.active_count()
        capa_db.aquecer()
        time.sleep(0.2)

        self.assertFalse(chamou.is_set(),
                         "tentou conectar sem servidor apontado")
        self.assertEqual(threading.active_count(), antes,
                         "criou thread para uma estação que não usa o banco")


class TestOArranqueAquece(unittest.TestCase):

    def test_o_main_aquece_antes_do_login(self):
        """O tempo morto do login é o único lugar em que a espera não incomoda.

        Depois do login já é tarde: a janela principal monta a lista de
        pacientes, e é ela que pagaria o tempo-limite. O teste lê o código
        porque rodar o ``main`` de verdade abriria o app.
        """
        fonte = fontes.texto("arranque.py")
        corpo = fonte[fonte.index("def main():"):]

        aquecer = corpo.find("capa_db.aquecer()")
        self.assertNotEqual(aquecer, -1, "o main() não aquece a conexão")

        login = corpo.find("DialogLogin()")
        self.assertNotEqual(login, -1, "não achei o login no main()")
        self.assertLess(aquecer, login,
                        "o aquecimento tem de vir ANTES do login — é o tempo "
                        "morto que ele aproveita")

    def test_salvar_a_configuracao_tambem_reabre_em_segundo_plano(self):
        """Trocar de servidor não pode empurrar o tempo-limite para a capa.

        ``_salvar`` chama ``capa_db.esquecer()``, que solta a conexão de
        propósito — o admin pode ter acabado de apontar OUTRO servidor. Sem
        aquecer logo em seguida, quem paga o primeiro connect do servidor novo
        é a próxima capa, na thread da interface: exatamente o defeito que o
        aquecimento existe para tirar do caminho.
        """
        # Por AST, e não por ``index("def _salvar")``: há DOIS ``_salvar`` no
        # administracao.py, e o primeiro é o de trocar senha. A primeira versão
        # deste teste casou com ele e falhou dizendo que faltava o esquecer.
        fonte = fontes.texto("administracao.py")
        corpo = ""
        for no in ast.walk(ast.parse(fonte)):
            if (isinstance(no, ast.FunctionDef) and no.name == "_salvar"
                    and "config_servico" in ast.get_source_segment(fonte, no)):
                corpo = ast.get_source_segment(fonte, no)
                break
        self.assertTrue(corpo, "não achei o _salvar da configuração do serviço")

        self.assertIn("capa_db.esquecer()", corpo)
        self.assertIn("capa_db.aquecer()", corpo,
                      "_salvar solta a conexão e não a reabre em segundo "
                      "plano — a próxima capa é que vai esperar")
        self.assertLess(corpo.index("capa_db.esquecer()"),
                        corpo.index("capa_db.aquecer()"),
                        "aquecer ANTES de esquecer abriria a conexão que o "
                        "esquecer joga fora em seguida")


if __name__ == "__main__":
    unittest.main()
