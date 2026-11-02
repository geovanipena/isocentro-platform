"""O núcleo contra o PostgreSQL de verdade: esquema, ``nucleo.gravar`` e o log (R-18).

O "pronto quando" da R-18 é provado AQUI, e não com SQLite nem com porta
falsa (AD-34): transação tudo-ou-nada, UPDATE/DELETE negados no log e o
verificador apontando a linha alterada. Gatilho, papel e GRANT só existem no
banco; um teste que os imitasse em Python provaria a imitação.

Roda com ``ISOCENTRO_PG_TESTE`` (conninfo de superusuário num cluster de
DESENVOLVIMENTO, em ``localhost``; roteiro no ``docs/AMBIENTE.md``). Cada
teste cria o próprio banco descartável e o apaga no fim. Sem a variável, a
classe é pulada com o motivo; com ela e o servidor fora, FALHA — quem
configurou o banco de teste quer saber que ele caiu.
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

from isocentro.adaptadores.postgres import esquema
from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo.gravacao import GravacaoRecusada, LinhaNova, gravar
from isocentro.nucleo.integridade import Ancora, verificar
from tests.pg_teste import (
    CONEXAO, MIGRACOES, ComBanco, precisa_do_postgres)


@precisa_do_postgres
class TestEsquema(ComBanco):

    def test_migracoes_e_versao_do_app_andam_juntas(self):
        """Arquivo novo em ``migracoes/`` sem subir o ``ESQUEMA_DO_APP``
        deixaria toda estação em somente leitura no banco migrado."""
        self.assertEqual(esquema.migracoes(MIGRACOES)[-1][0],
                         esquema.ESQUEMA_DO_APP)

    def test_banco_na_versao_do_app_grava(self):
        s = esquema.conferir(self.app)
        self.assertEqual((s.versao_do_banco, s.somente_leitura, s.aviso),
                         (esquema.ESQUEMA_DO_APP, False, None))

    def test_versao_diferente_abre_somente_leitura(self):
        for esperada in (esquema.ESQUEMA_DO_APP + 1, esquema.ESQUEMA_DO_APP - 1):
            with self.subTest(esperada=esperada):
                s = esquema.conferir(self.app, esperada=esperada)
                self.assertTrue(s.somente_leitura)
                self.assertIn("atualiz", s.aviso)

    def test_banco_sem_esquema_abre_somente_leitura(self):
        with psycopg.connect(make_conninfo(CONEXAO, dbname="postgres"),
                             autocommit=True) as c:
            s = esquema.conferir(c)
        self.assertEqual((s.versao_do_banco, s.somente_leitura), (None, True))

    def test_aplicar_de_novo_nao_faz_nada(self):
        with self.banco.conectar() as c:
            self.assertEqual(esquema.aplicar(c, MIGRACOES), [])

    def test_migracao_que_falha_nao_deixa_metade(self):
        """Arquivo que quebra na 2ª instrução: sem a transação por arquivo,
        a 1ª ficaria no banco e a versão não — e a próxima tentativa
        tropeçaria na tabela que já existe."""
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, True)
        for _, arquivo in esquema.migracoes(MIGRACOES):
            shutil.copy(arquivo, pasta)
        seguinte = esquema.ESQUEMA_DO_APP + 1
        (pasta / f"{seguinte:04d}_quebrada.sql").write_text(
            "CREATE TABLE nucleo.meia (a int);\nSELECT 1/0;\n", encoding="utf-8")
        with self.banco.conectar() as c:
            with self.assertRaises(psycopg.Error):
                esquema.aplicar(c, pasta)
            self.assertEqual(esquema.versao_do_banco(c), esquema.ESQUEMA_DO_APP)
            self.assertIsNone(c.execute(
                "SELECT to_regclass('nucleo.meia')").fetchone()[0])

    def test_app_nao_muda_o_esquema(self):
        for ddl in ("CREATE SCHEMA invasor",
                    "CREATE TABLE nucleo.invasora (a int)",
                    "CREATE TABLE public.invasora (a int)",
                    "ALTER TABLE nucleo.log DISABLE TRIGGER log_imutavel",
                    "DROP TABLE nucleo.log"):
            with self.subTest(ddl):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    self.app.execute(ddl)


@precisa_do_postgres
class TestGravacao(ComBanco):

    def test_grava_dado_e_log(self):
        g = self._gravar(versao_origem="RTPLAN 1.2.840.1 2026-10-27")
        self.assertEqual((g.tabela, g.posicao), ("teste.coisa", 1))
        with self.banco.conectar() as c:
            linha = c.execute(
                "SELECT quem, modulo, tabela, registro, versao_origem"
                " FROM nucleo.log").fetchone()
        self.assertEqual(linha, ("geovani.pena", "teste", "teste.coisa",
                                 g.registro, "RTPLAN 1.2.840.1 2026-10-27"))

    def test_falha_no_registro_nao_deixa_log(self):
        self._gravar("a")
        with self.assertRaises(GravacaoRecusada):
            self._gravar("falha")
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 1)
        self.assertEqual(self._conta("SELECT posicao FROM nucleo.ponta"), 1)

    def test_falha_no_log_desfaz_o_registro(self):
        """O registro entra primeiro; o gatilho do log recusa depois (correção
        de um id que não existe). Sem a transação única, o dado ficaria no
        banco sem autoria nenhuma."""
        with self.assertRaises(GravacaoRecusada):
            self._gravar("b", substitui="999")
        self.assertEqual(self._conta("SELECT count(*) FROM teste.coisa"), 0)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 0)

    def test_tabela_alheia_e_recusada_pelo_banco(self):
        """Pela porta direto, sem o ``nucleo.gravar``: a recusa tem de vir do
        gatilho, porque um módulo que pule o núcleo não passa pela do Python."""
        linha = LinhaNova("geovani.pena", "teste", "outro.coisa", None, None)
        with self.assertRaises(GravacaoRecusada):
            self.porta.inserir_com_log("outro.coisa", {"valor": "x"}, linha)
        self.assertEqual(self._conta("SELECT count(*) FROM outro.coisa"), 0)

    def test_correcao_e_registro_novo_e_o_vigente_e_calculado(self):
        a = self._gravar("a")
        b = self._gravar("b")
        a2 = self._gravar("a corrigido", substitui=a.registro)
        self.assertEqual(self.porta.vigentes("teste.coisa"),
                         [b.registro, a2.registro])
        self.assertEqual(self._conta("SELECT count(*) FROM teste.coisa"), 3)

    def test_o_mesmo_registro_nao_se_corrige_duas_vezes(self):
        a = self._gravar("a")
        self._gravar("a2", substitui=a.registro)
        with self.assertRaises(GravacaoRecusada):
            self._gravar("a3", substitui=a.registro)

    def test_app_nao_escreve_o_hash_nem_a_posicao(self):
        for insercao in (
                "INSERT INTO nucleo.log (posicao, quem, modulo, tabela, registro)"
                " VALUES (99, 'x', 'teste', 'teste.coisa', '1')",
                "INSERT INTO nucleo.log (hash, quem, modulo, tabela, registro)"
                " VALUES ('\\x00', 'x', 'teste', 'teste.coisa', '1')",
                "UPDATE nucleo.ponta SET posicao = 0",
                "INSERT INTO nucleo.dono_tabela VALUES ('teste.nova', 'teste')"):
            with self.subTest(insercao):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    self.app.execute(insercao)

    def test_dado_registrado_nao_se_edita_nem_se_apaga(self):
        self._gravar("a")
        for comando in ("UPDATE teste.coisa SET valor = 'b'",
                        "DELETE FROM teste.coisa"):
            with self.subTest(comando):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    self.app.execute(comando)


@precisa_do_postgres
class TestLogImutavel(ComBanco):

    def test_update_delete_truncate_negados_ao_app_e_a_concentradora(self):
        self._gravar("a")
        for papel in ("isocentro_app", "isocentro_concentradora"):
            with self.banco.conectar(papel) as c:
                for comando in ("UPDATE nucleo.log SET quem = 'outro'",
                                "DELETE FROM nucleo.log",
                                "TRUNCATE nucleo.log"):
                    with self.subTest(papel=papel, comando=comando):
                        with self.assertRaises(
                                psycopg.errors.InsufficientPrivilege):
                            c.execute(comando)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 1)

    def test_nem_o_dono_edita_o_log_sem_desligar_o_gatilho(self):
        self._gravar("a")
        with self.banco.conectar("isocentro_dono") as c:
            for comando in ("UPDATE nucleo.log SET quem = 'outro'",
                            "DELETE FROM nucleo.log",
                            "TRUNCATE nucleo.log"):
                with self.subTest(comando):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        c.execute(comando)


@precisa_do_postgres
class TestCorrente(ComBanco):

    def _gravar_varias(self, n):
        return [self._gravar(f"v{i}") for i in range(n)]

    def _adulterar(self, *comandos):
        """Como faria quem tem DDL: desliga o gatilho, mexe, religa."""
        with self.banco.conectar() as c:
            c.execute("ALTER TABLE nucleo.log DISABLE TRIGGER log_imutavel")
            for comando in comandos:
                c.execute(comando)
            c.execute("ALTER TABLE nucleo.log ENABLE TRIGGER log_imutavel")

    def test_corrente_do_banco_fecha_no_verificador(self):
        """A conta do gatilho e a do Python são a mesma, inclusive com acento
        e fora do plano básico do Unicode: se divergissem, todo log íntegro
        seria acusado."""
        gravar(self.porta, modulo="teste", tabela="teste.coisa",
               dados={"valor": "x"}, quem="física ção 😀",
               versao_origem="ação")
        self._gravar_varias(4)
        self.assertEqual(verificar(self.porta.linhas_do_log()), [])

    def test_linha_alterada_e_apontada_com_registro_e_posicao(self):
        gravados = self._gravar_varias(5)
        self._adulterar("UPDATE nucleo.log SET quem = 'outra pessoa'"
                        " WHERE posicao = 3")
        achados = verificar(self.porta.linhas_do_log())
        self.assertEqual([(d.posicao, d.registro) for d in achados],
                         [(3, gravados[2].registro)])

    def test_linha_apagada_e_apontada(self):
        self._gravar_varias(5)
        self._adulterar("DELETE FROM nucleo.log WHERE posicao = 2")
        achados = verificar(self.porta.linhas_do_log())
        self.assertEqual(achados[0].posicao, 2)
        self.assertIn("apagada", achados[0].motivo)

    def test_corrente_refeita_por_inteiro_so_a_ancora_pega(self):
        """O pior caso: altera a linha 2 e refaz os hashes dali em diante com
        a própria função do banco. O verificador sozinho não vê; a âncora
        tirada antes vê."""
        self._gravar_varias(5)
        ancora = Ancora(5, self.porta.linhas_do_log()[-1].hash)
        refazer = [
            "UPDATE nucleo.log SET quem = 'outra pessoa' WHERE posicao = 2"]
        for p in range(2, 6):
            refazer.append(
                "UPDATE nucleo.log SET hash_anterior ="
                f" (SELECT hash FROM nucleo.log WHERE posicao = {p - 1})"
                f" WHERE posicao = {p}")
            refazer.append(
                "UPDATE nucleo.log l SET hash = nucleo.hash_da_linha(l)"
                f" WHERE posicao = {p}")
        self._adulterar(*refazer)
        linhas = self.porta.linhas_do_log()
        self.assertEqual(verificar(linhas), [])
        self.assertEqual([d.posicao for d in verificar(linhas, [ancora])], [5])

    def test_duas_estacoes_ao_mesmo_tempo_nao_bifurcam(self):
        """Sem a trava da ponta, duas transações leem o mesmo "último hash" e
        encadeiam nele: a corrente se bifurca e a posição se repete."""
        erros = []

        def estacao(papel):
            try:
                with self.banco.conectar(papel) as c:
                    porta = PortaPostgres(c)
                    for i in range(15):
                        gravar(porta, modulo="teste", tabela="teste.coisa",
                               dados={"valor": f"{papel}{i}"}, quem=papel)
            except Exception as erro:  # noqa: BLE001 - relatado no assert abaixo
                erros.append(erro)

        threads = [threading.Thread(target=estacao, args=(p,))
                   for p in ("isocentro_app", "isocentro_concentradora")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        self.assertEqual(erros, [])
        linhas = self.porta.linhas_do_log()
        self.assertEqual([l.posicao for l in linhas], list(range(1, 31)))
        self.assertEqual(verificar(linhas), [])


if __name__ == "__main__":
    unittest.main()
