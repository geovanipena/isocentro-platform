"""Histórico de uso (append JSONL, usuário atual, leitura).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import ambiente  # noqa: E402
from isocentro.dados import historico  # noqa: E402


def _devolver_log_dir(antes) -> None:
    """Devolve a variável como estava — nunca só ``pop``.

    O ``pop`` desligava o desvio da suíte (``limpeza_de_tela``): os testes de
    tela que rodavam depois deste arquivo voltavam a gravar no histórico real.
    """
    if antes is None:
        os.environ.pop("ISOCENTRO_LOG_DIR", None)
    else:
        os.environ["ISOCENTRO_LOG_DIR"] = antes


class TestSuiteNaoGravaNoHistoricoReal(unittest.TestCase):
    """A suíte escrevia no ``historico_uso.jsonl`` da estação.

    Medido em 13/10/2026: ~96% das linhas do arquivo eram de teste ("app_fechado"
    e "capa_montada" com usuário vazio), e o uso real do app não se distinguia
    do ruído.
    """

    def test_apoio_de_tela_desvia_o_historico(self):
        import tests.limpeza_de_tela as limpeza
        from isocentro.dados import indice

        caminho = Path(historico.caminho_log()).resolve()
        self.assertNotEqual(caminho.parent, Path(indice._app_dir()).resolve())
        self.assertEqual(os.environ.get("ISOCENTRO_LOG_DIR"),
                         limpeza.PASTA_HISTORICO)
        # Até 15/10/2026 o desvio ia pelo nome ANTIGO, e um nome mais novo
        # definido na estação o derrotava; daí a conferência de que ele estava
        # vazio. Hoje o desvio vai pelo ISOCENTRO_, que é o de maior
        # precedência: nenhum outro nome passa na frente dele.
        self.assertEqual(ambiente.nome_novo("FICHAPY_LOG_DIR"), "ISOCENTRO_LOG_DIR")


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.mkdtemp()
        self._antes = os.environ.get("ISOCENTRO_LOG_DIR")
        os.environ["ISOCENTRO_LOG_DIR"] = self._d
        historico.definir_usuario(None)

    def tearDown(self):
        _devolver_log_dir(self._antes)
        historico.definir_usuario(None)

    def test_vazio(self):
        self.assertEqual(historico.ler(), [])

    def test_registrar_e_ler_mais_recente_primeiro(self):
        historico.registrar("login", usuario={"usuario": "ana"})
        historico.registrar("ficha_gerada", detalhes={"registro": "123"},
                            usuario={"usuario": "ana"})
        eventos = historico.ler()
        self.assertEqual(len(eventos), 2)
        self.assertEqual(eventos[0]["evento"], "ficha_gerada")   # mais recente
        self.assertEqual(eventos[0]["detalhes"]["registro"], "123")
        self.assertEqual(eventos[1]["evento"], "login")
        self.assertTrue(all(e["usuario"] == "ana" for e in eventos))

    def test_usuario_atual_padrao(self):
        historico.definir_usuario({"usuario": "bruno", "nome": "Bruno"})
        historico.registrar("reindexacao")
        self.assertEqual(historico.ler()[0]["usuario"], "bruno")

    def test_append_nao_reescreve(self):
        for i in range(5):
            historico.registrar("evt", detalhes={"i": i}, usuario="x")
        # cada registrar é uma linha; o arquivo tem 5 linhas
        p = Path(historico.caminho_log())
        linhas = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(linhas), 5)

    def test_linha_corrompida_e_pulada(self):
        historico.registrar("ok", usuario="x")
        p = Path(historico.caminho_log())
        with open(p, "a", encoding="utf-8") as f:
            f.write("isto não é json\n")
        historico.registrar("ok2", usuario="x")
        eventos = historico.ler()
        self.assertEqual([e["evento"] for e in eventos], ["ok2", "ok"])

    def test_registrar_nunca_levanta(self):
        # base dentro de um ARQUIVO (não um diretório) → mkdir falha, mas o
        # registrar engole o erro (histórico é acessório).
        arq = os.path.join(self._d, "arquivo")
        open(arq, "w").close()
        os.environ["ISOCENTRO_LOG_DIR"] = os.path.join(arq, "sub")
        try:
            historico.registrar("x")   # não deve levantar
        finally:
            os.environ["ISOCENTRO_LOG_DIR"] = self._d


class TestFichasDoUsuario(unittest.TestCase):
    """A lista "Suas últimas fichas" da tela Fichinha.

    O log é COMPARTILHADO entre as estações; o que dá utilidade à lista é o
    recorte por usuário e por paciente — a ficha do colega e a terceira versão
    do mesmo caso são exatamente o que não se quer ver ali.
    """

    def setUp(self):
        self._d = tempfile.mkdtemp()
        self._antes = os.environ.get("ISOCENTRO_LOG_DIR")
        os.environ["ISOCENTRO_LOG_DIR"] = self._d
        historico.definir_usuario(None)

    def tearDown(self):
        _devolver_log_dir(self._antes)
        historico.definir_usuario(None)

    def _evento(self, em, usuario, evento="ficha_gerada", **detalhes):
        """Escreve uma linha crua: o ``em`` precisa ser escolhido pelo teste."""
        linha = {"em": em, "usuario": usuario, "evento": evento,
                 "detalhes": detalhes}
        with open(historico.caminho_log(), "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    @staticmethod
    def _hoje(hora="10:00:00"):
        return f"{datetime.date.today().isoformat()}T{hora}"

    @staticmethod
    def _dias_atras(n, hora="10:00:00"):
        d = datetime.date.today() - datetime.timedelta(days=n)
        return f"{d.isoformat()}T{hora}"

    def test_so_do_usuario_logado(self):
        self._evento(self._hoje("08:00:00"), "ana", paciente="ANA PAC",
                     registro="1")
        self._evento(self._hoje("09:00:00"), "bruno", paciente="BRUNO PAC",
                     registro="2")
        res = historico.fichas_do_usuario("ana")
        self.assertEqual([r["registro"] for r in res["recentes"]], ["1"])

    def test_usuario_case_insensitive(self):
        self._evento(self._hoje(), "Ana", paciente="X", registro="1")
        res = historico.fichas_do_usuario({"usuario": "ana"})
        self.assertEqual(len(res["recentes"]), 1)

    def test_uma_linha_por_paciente_na_versao_mais_recente(self):
        self._evento(self._hoje("08:00:00"), "ana", paciente="P", registro="9",
                     versao=1)
        self._evento(self._hoje("09:00:00"), "ana", paciente="P", registro="9",
                     versao=2)
        res = historico.fichas_do_usuario("ana")
        self.assertEqual(len(res["recentes"]), 1)
        self.assertEqual(res["recentes"][0]["versao"], 2)

    def test_so_a_ficha_definitiva_conta(self):
        """Montar e conferir não é ter entregado."""
        self._evento(self._hoje(), "ana", evento="ficha_automatica", nome="P")
        self._evento(self._hoje(), "ana", evento="ficha_visualizada",
                     paciente="P", registro="9")
        self.assertEqual(historico.fichas_do_usuario("ana")["recentes"], [])

    def test_mais_recente_primeiro_e_limite(self):
        # Escritos do mais antigo para o mais novo, como o log append-only de
        # verdade: a ordem da lista é a do ARQUIVO, não a do carimbo de hora.
        for i in range(14, -1, -1):
            self._evento(self._dias_atras(i), "ana", paciente=f"P{i}",
                         registro=str(i))
        res = historico.fichas_do_usuario("ana", limite=10)
        self.assertEqual([r["registro"] for r in res["recentes"]],
                         [str(i) for i in range(10)])

    def test_contador_de_hoje_conta_alem_do_limite(self):
        """O número do dia é do dia inteiro, não do que coube na lista."""
        for i in range(12):
            self._evento(self._hoje(f"{8 + i // 4:02d}:00:00"), "ana",
                         paciente=f"P{i}", registro=str(i))
        self._evento(self._dias_atras(1), "ana", paciente="ONTEM",
                     registro="99")
        res = historico.fichas_do_usuario("ana", limite=10)
        self.assertEqual(len(res["recentes"]), 10)
        self.assertEqual(res["hoje"], 12)

    def test_pasta_vem_junto(self):
        self._evento(self._hoje(), "ana", paciente="P", registro="9",
                     pasta=r"C:\casos\P")
        self.assertEqual(historico.fichas_do_usuario("ana")["recentes"][0]
                         ["pasta"], r"C:\casos\P")

    def test_evento_antigo_sem_pasta_nao_quebra(self):
        self._evento(self._hoje(), "ana", paciente="P", registro="9")
        self.assertEqual(historico.fichas_do_usuario("ana")["recentes"][0]
                         ["pasta"], "")

    def test_usuario_atual_e_o_padrao(self):
        historico.definir_usuario({"usuario": "ana"})
        self._evento(self._hoje(), "ana", paciente="P", registro="1")
        self._evento(self._hoje(), "bruno", paciente="Q", registro="2")
        res = historico.fichas_do_usuario()
        self.assertEqual([r["registro"] for r in res["recentes"]], ["1"])

    def test_log_inexistente(self):
        res = historico.fichas_do_usuario("ana")
        self.assertEqual(res, {"recentes": [], "hoje": 0})


if __name__ == "__main__":
    unittest.main()
