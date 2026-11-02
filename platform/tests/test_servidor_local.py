"""Servidor LOCAL de demonstração: a tradução de T-SQL e as telas com dado.

O que se protege aqui é o modo de falha deste recurso: o app ganha uma consulta
com um pedaço de T-SQL que a tradução não cobre, a consulta vira
``FalhaDeLeitura``, e a tela correspondente aparece VAZIA justamente na frente
de quem assiste à demonstração — sem erro nenhum, porque vazio é um estado
legítimo das telas. Por isso o teste de ponta a ponta monta um servidor de
verdade (só com figurantes, sem dado de paciente) e chama as funções do app.
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

from isocentro.banco import banco_local, capa_db, servidor_local  # noqa: E402

import montar_servidor_local as montador  # noqa: E402

# Os três nomes de cada uma (ISOCENTRO_, RADIOTERAFICHA_, FICHAPY_): limpar só
# o atual deixaria a variável antiga de uma estação valendo no teste.
_VARIAVEIS = tuple(nome for sufixo in (
    "BANCO_LOCAL", "LISTA_EXPERIMENTAL", "ATIVIDADES_EXPERIMENTAL",
    "GATILHO_EXPERIMENTAL", "DB_SERVIDOR")
    for nome in (f"ISOCENTRO_{sufixo}", f"RADIOTERAFICHA_{sufixo}", f"FICHAPY_{sufixo}"))


class TestTraducao(unittest.TestCase):
    """Cada pedaço de T-SQL que o app usa, e o que ele vira."""

    def test_top_vira_limit_no_fim(self):
        sql = servidor_local.traduzir("SELECT TOP 1 a FROM DWH.T WHERE x = ?")
        self.assertNotIn("TOP", sql)
        self.assertTrue(sql.rstrip().endswith("LIMIT 1"))
        self.assertIn("FROM T", sql)

    def test_top_com_distinct(self):
        sql = servidor_local.traduzir("SELECT DISTINCT TOP 5 a FROM T")
        self.assertIn("SELECT DISTINCT", sql)
        self.assertTrue(sql.rstrip().endswith("LIMIT 5"))

    def test_convert_112_de_expressao_com_parenteses(self):
        sql = servidor_local.traduzir(
            "SELECT CONVERT(char(8), MIN(th.T), 112) FROM F th")
        self.assertIn("strftime('%Y%m%d', MIN(th.T))", sql)

    def test_convert_de_outro_estilo_falha_em_vez_de_chutar(self):
        with self.assertRaises(ValueError):
            servidor_local.traduzir("SELECT CONVERT(char(10), x, 103) FROM T")

    def test_datediff_dentro_de_dateadd(self):
        """A consulta de idade do resumo do mês aninha as duas."""
        sql = servidor_local.traduzir(
            "SELECT DATEADD(YEAR, DATEDIFF(YEAR, d, GETDATE()), d) FROM T")
        self.assertIn("DATEADD_('YEAR', DATEDIFF_('YEAR', d, GETDATE_()), d)",
                      sql)

    def test_cast_as_date_e_os_outros_cast(self):
        sql = servidor_local.traduzir(
            "SELECT CAST(x AS float) FROM T WHERE CAST(t.A AS date) = ?")
        self.assertIn("date(t.A) = ?", sql)
        self.assertIn("CAST(x AS float)", sql)

    def test_isnull_n_aspas_e_comentario(self):
        sql = servidor_local.traduzir(
            "SELECT ISNULL(a, 0) -- o (comentário) não atrapalha\n"
            "FROM T WHERE b LIKE N'%INICIO%'")
        self.assertIn("IFNULL(a, 0)", sql)
        self.assertIn("LIKE '%INICIO%'", sql)
        self.assertNotIn("comentário", sql)

    def test_idade_pela_conta_do_sql_server(self):
        cx = servidor_local.Conexao(":memory:")
        idade = cx.cursor().execute(
            "SELECT DATEDIFF(YEAR, ?, ?) - CASE WHEN DATEADD(YEAR, "
            "DATEDIFF(YEAR, ?, ?), ?) > ? THEN 1 ELSE 0 END",
            *(["1960-12-31 00:00:00", "2026-06-01 00:00:00"] * 2),
            "1960-12-31 00:00:00", "2026-06-01 00:00:00").fetchone()[0]
        self.assertEqual(idade, 65)

    def test_data_volta_como_datetime(self):
        cx = servidor_local.Conexao(":memory:")
        valor = cx.cursor().execute("SELECT '2026-09-29 07:36:00'").fetchone()[0]
        self.assertEqual(valor, dt.datetime(2026, 9, 29, 7, 36))


class TestServidorMontado(unittest.TestCase):
    """Um servidor montado só com figurantes, e as telas perguntando a ele."""

    @classmethod
    def setUpClass(cls):
        # ``ignore_cleanup_errors``: no Windows um arquivo ainda aberto por uma
        # conexão que o coletor não recolheu trava a remoção, e isso não é
        # falha do que esta classe testa.
        cls._pasta = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.arquivo = Path(cls._pasta.name) / "dw.sqlite"
        agora = dt.datetime.combine(dt.date.today(), dt.time(10, 30))
        m = montador.Montador(agora)
        for nome in ("A. Ramos Junior, Rubens", "Barcelos, Sarah"):
            m.id_doutor(nome)
        for mq in montador.MAQUINAS:
            m.por("InSightiveResourceMachine", mq[0], mq[1], mq[2], "Active",
                  "Dispositivo de radiação")
        agenda: list = []
        figurantes = montador.lancar_figurantes(m, 40, agenda, {})
        montador.lancar_agenda(m, agenda)
        infos = [{"registro": f["registro"], "dim": f["dim"],
                  "cenario": "vai_comecar" if i < 2 else "concluido",
                  "fim": agora} for i, f in enumerate(figurantes[:4])]
        montador.lancar_atividades(m, infos, figurantes[4:])
        m.gravar(cls.arquivo, {"tipo": servidor_local.TIPO,
                               "versao": servidor_local.VERSAO,
                               "montado_em": agora.isoformat()})

    @classmethod
    def tearDownClass(cls):
        banco_local.esquecer()
        cls._pasta.cleanup()

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in _VARIAVEIS}

    def tearDown(self):
        capa_db.esquecer()
        for chave, valor in self._env.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor

    def test_o_arquivo_se_declara_servidor_local(self):
        self.assertEqual(servidor_local.tipo_do_arquivo(self.arquivo),
                         servidor_local.TIPO)

    def test_toda_consulta_das_telas_responde(self):
        """Nenhuma consulta pode FALHAR. Zero só onde o dado não existe: o
        gatilho, sem RTPLAN de verdade num servidor só de figurantes."""
        linhas = montador.conferir(self.arquivo)
        falhas = [(nome, erro) for nome, n, erro in linhas if n < 0]
        self.assertEqual(falhas, [])
        vazias = {nome for nome, n, _ in linhas if n == 0}
        for obrigatoria in ("capa: pacientes", "virtual: em tratamento",
                            "agenda: hoje", "agenda: máquinas",
                            "atividades: documentação", "atividades: altas"):
            self.assertNotIn(obrigatoria, vazias)

    def test_a_tela_anuncia_que_e_demonstracao(self):
        os.environ["ISOCENTRO_BANCO_LOCAL"] = str(self.arquivo)
        situacao, recado = capa_db.estado()
        self.assertEqual(situacao, "local")
        self.assertIn("SERVIDOR LOCAL", recado)

    def test_somente_leitura(self):
        cx = servidor_local.Conexao(self.arquivo)
        try:
            with self.assertRaises(sqlite3.Error):
                cx.cursor().execute("DELETE FROM DimPatient")
        finally:
            # Fechada aqui: aberta, ela segura o arquivo e o Windows não deixa
            # apagar a pasta temporária no fim da classe.
            cx.close()


if __name__ == "__main__":
    unittest.main()
