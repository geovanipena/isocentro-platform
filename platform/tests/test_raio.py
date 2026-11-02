# -*- coding: utf-8 -*-
"""O raio de revisão do diff (``tools/raio.py``, AD-39).

O defeito que importa aqui é o raio que ENCOLHE: um arquivo que devia pedir a
suíte inteira e sai como "o módulo", ou uma mudança que chega ao papel sem o
aviso de comparar o PDF. Os testes conferem os dois sentidos — o que soma e o
que nunca pode ser cortado.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

import raio  # noqa: E402
import testar  # noqa: E402
from raio import CONSUMIDORES, MODULO, NENHUM, TUDO  # noqa: E402


def _cls(rel):
    dono, nivel, _ = raio.classificar_caminho(rel)
    return dono, nivel


class TestClassificarCaminho(unittest.TestCase):

    def test_papel_e_do_radioteraficha(self):
        self.assertEqual(_cls("isocentro/papel/ficha_pdf.py"),
                         ("radioteraficha", MODULO))

    def test_paralelo_e_qualidade_sao_do_plano(self):
        for nome in ("paralelo", "qualidade", "qualidade_metodo"):
            self.assertEqual(_cls(f"isocentro/dominio/{nome}.py"),
                             ("plano", MODULO))

    def test_dicom_vale_rt_e_portanto_tudo(self):
        """A semente DIVIDE o dicom/; enquanto não está dividido, o pedaço
        mais largo (rt) vale o arquivo inteiro — senão um SSD mexido no
        dicom_rt sairia como mudança local."""
        for nome in ("dicom_rt", "dvh", "cortes", "ct_series", "__init__"):
            self.assertEqual(_cls(f"isocentro/dicom/{nome}.py"), ("rt", TUDO))

    def test_equipe_e_maquina_sao_do_nucleo(self):
        self.assertEqual(_cls("isocentro/dados/equipe.py"), ("nucleo", TUDO))
        self.assertEqual(_cls("isocentro/dominio/constantes.py"), ("nucleo", TUDO))

    def test_rt_nucleo_adaptadores_valem_tudo(self):
        for rel in ("isocentro/rt/margem.py", "isocentro/nucleo/motor.py",
                    "isocentro/adaptadores/dicom/leitura.py"):
            self.assertEqual(_cls(rel)[1], TUDO, rel)

    def test_fachada_e_manifesto_pedem_consumidores(self):
        self.assertEqual(_cls("isocentro/modulos/plano/consulta.py"),
                         ("plano", CONSUMIDORES))
        self.assertEqual(_cls("isocentro/modulos/plano/__init__.py"),
                         ("plano", CONSUMIDORES))
        self.assertEqual(_cls("isocentro/modulos/plano/calculo.py"),
                         ("plano", MODULO))
        # o __init__ de um SUBpacote não é o manifesto
        self.assertEqual(_cls("isocentro/modulos/plano/sub/__init__.py"),
                         ("plano", MODULO))

    def test_tela_do_modulo_herda_o_modulo(self):
        self.assertEqual(_cls("isocentro/interface/modulos/plano/tela.py"),
                         ("plano", MODULO))

    def test_sql_dependencia_e_tabela_de_maquina_valem_tudo(self):
        for rel in ("migracoes/0001_inicial.sql", "migracoes/LEIA.txt",
                    "isocentro/modulos/plano/consulta.sql",
                    "requirements.txt", "constraints.txt", "Isocentro.spec",
                    "pyproject.toml",
                    "TrueBeamSN1001__6MV__TMR.csv",
                    # dentro de um módulo continua sendo tabela de máquina
                    "isocentro/modulos/plano/TrueBeam__10MV__SCP.csv",
                    "dados_feixe/qualquer.csv"):
            self.assertEqual(_cls(rel)[1], TUDO, rel)

    def test_sem_dono_vale_tudo(self):
        """O que a semente ainda não decidiu (Q6) não pode sair barato."""
        for rel in ("isocentro/banco/capa_db.py", "isocentro/dados/auth.py",
                    "isocentro/interface/gui.py", "isocentro/raiz.py",
                    "isocentro/composicao.py", "run_gui.py", ".gitignore",
                    "assets/logo.png", "tools/gerar_executavel.py",
                    "isocentro/modulos/plano"):
            self.assertEqual(_cls(rel)[1], TUDO, rel)

    def test_teste_ferramenta_e_documento(self):
        self.assertEqual(_cls("tests/test_capa.py"), ("tests/test_capa.py", MODULO))
        self.assertEqual(_cls("tests/limpeza_de_tela.py")[1], TUDO)
        self.assertEqual(_cls("tools/mapa.py"), ("tools/mapa.py", MODULO))
        self.assertEqual(_cls("NOTAS.md")[1], NENHUM)
        self.assertEqual(_cls("docs/AMBIENTE.md")[1], NENHUM)
        # Markdown que vai no pacote não é "só documento"
        self.assertEqual(_cls("assets/ajuda.md")[1], TUDO)
        # nem a fonte da classe 62304: rebaixar classe ali não sai barato
        self.assertEqual(_cls("docs/qms/classificacao-62304.md")[1], TUDO)

    def test_barra_invertida_do_windows(self):
        item, = raio.avaliar(["isocentro\\papel\\rodape.py"],
                             raio.Grafo({}, {}, {}))
        self.assertEqual((item.arquivo, item.dono), ("isocentro/papel/rodape.py",
                                                     "radioteraficha"))

    def test_a_tabela_de_destino_aponta_arquivo_que_existe(self):
        """Quando o R-58 mover estes arquivos, a tabela tem de mudar junto:
        um caminho velho na tabela faria o arquivo novo cair em outra regra
        sem ninguém perceber."""
        for rel in raio._DESTINO_ARQUIVO:
            self.assertTrue((RAIZ / rel).is_file(), rel)
        for pasta in raio._DESTINO_PASTA:
            self.assertTrue((RAIZ / pasta).is_dir(), pasta)


class _Arvore(unittest.TestCase):
    """Repositório de mentira: ``isocentro/`` com os imports que o teste pede."""

    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="raio_"))
        self.addCleanup(shutil.rmtree, self.raiz, True)

    def escrever(self, rel, texto=""):
        arq = self.raiz / rel
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(texto, encoding="utf-8")


class TestPapel(_Arvore):

    def setUp(self):
        super().setUp()
        for pac in ("isocentro", "isocentro/papel", "isocentro/dicom",
                    "isocentro/interface", "isocentro/banco"):
            self.escrever(f"{pac}/__init__.py")
        self.escrever("isocentro/papel/ficha_pdf.py",
                      "from isocentro.dicom import dicom_rt\nfrom . import rodape\n")
        self.escrever("isocentro/papel/rodape.py", "import isocentro.raiz\n")
        self.escrever("isocentro/raiz.py")
        self.escrever("isocentro/dicom/dicom_rt.py", "from .dvh import calcular\n")
        self.escrever("isocentro/dicom/dvh.py", "def calcular(): pass\n")
        self.escrever("isocentro/interface/edicao.py",
                      "def f():\n    from isocentro.papel.ficha_pdf import gerar\n")
        self.escrever("isocentro/banco/agenda_db.py", "import os\n")
        self.grafo = raio.montar_grafo(self.raiz)

    def test_o_que_o_papel_importa_alcanca_o_papel(self):
        """Inclusive por import relativo e em dois passos (dvh → dicom_rt →
        ficha): o DVH muda o número da ficha sem a ficha mudar."""
        alc = raio.alcanca_papel(self.grafo)
        for rel in ("isocentro/dicom/dicom_rt.py", "isocentro/dicom/dvh.py",
                    "isocentro/raiz.py", "isocentro/papel/rodape.py"):
            self.assertIn(rel, alc)

    def test_quem_importa_o_papel_alcanca_o_papel(self):
        """Import tardio, dentro de função: é o jeito da tela de edição."""
        self.assertIn("isocentro/interface/edicao.py",
                      raio.alcanca_papel(self.grafo))

    def test_o_que_nao_tem_caminho_nao_alcanca(self):
        self.assertNotIn("isocentro/banco/agenda_db.py",
                         raio.alcanca_papel(self.grafo))

    def test_papel_soma_ao_raio_sem_mudar_o_nivel(self):
        itens = raio.avaliar(["isocentro/papel/rodape.py",
                              "isocentro/banco/agenda_db.py",
                              "assets/logo.png"], self.grafo)
        por = {i.arquivo: i for i in itens}
        self.assertTrue(por["isocentro/papel/rodape.py"].papel)
        self.assertEqual(por["isocentro/papel/rodape.py"].nivel, MODULO)
        self.assertFalse(por["isocentro/banco/agenda_db.py"].papel)
        self.assertTrue(por["assets/logo.png"].papel)
        texto = raio.relatorio(itens, "HEAD")
        self.assertIn("comparar_pdf", texto)
        self.assertIn("AVISAR", texto)

    def test_arquivo_quebrado_nao_derruba_o_grafo(self):
        self.escrever("isocentro/banco/quebrado.py", "def (:\n")
        grafo = raio.montar_grafo(self.raiz)
        self.assertIn("isocentro.banco.quebrado", grafo.caminho)


class TestConsumidoresERecorte(_Arvore):

    def setUp(self):
        super().setUp()
        self.escrever("isocentro/__init__.py")
        self.escrever("isocentro/modulos/__init__.py")
        self.escrever("isocentro/modulos/plano/__init__.py")
        self.escrever("isocentro/modulos/plano/consulta.py",
                      "from .calculo import um\n")
        self.escrever("isocentro/modulos/plano/calculo.py")
        self.escrever("isocentro/modulos/tratamento/__init__.py")
        self.escrever("isocentro/modulos/tratamento/agenda.py",
                      "from isocentro.modulos.plano.consulta import um\n")
        self.escrever("isocentro/modulos/tratamento/sessao.py")
        self.escrever("isocentro/modulos/qualidade/__init__.py")
        self.escrever("isocentro/modulos/qualidade/cq.py")
        self.escrever("tests/test_plano.py")
        self.grafo = raio.montar_grafo(self.raiz)

    def test_fachada_lista_quem_a_importa_de_fora(self):
        item, = raio.avaliar(["isocentro/modulos/plano/consulta.py"], self.grafo)
        self.assertEqual(item.nivel, CONSUMIDORES)
        self.assertEqual(item.consumidores,
                         ("isocentro/modulos/tratamento/agenda.py",))
        self.assertIn("motor", raio.relatorio([item], "HEAD"))

    def test_recorte_da_fachada_leva_o_modulo_consumidor_inteiro(self):
        itens = raio.avaliar(["isocentro/modulos/plano/consulta.py"], self.grafo)
        rec = raio.recorte(itens, self.raiz)
        self.assertIn("isocentro/modulos/plano/calculo.py", rec)
        self.assertIn("isocentro/modulos/tratamento/sessao.py", rec)
        self.assertNotIn("isocentro/modulos/qualidade/cq.py", rec)

    def test_recorte_interno_e_so_o_modulo(self):
        itens = raio.avaliar(["isocentro/modulos/plano/calculo.py"], self.grafo)
        rec = raio.recorte(itens, self.raiz)
        self.assertIn("isocentro/modulos/plano/consulta.py", rec)
        self.assertNotIn("isocentro/modulos/tratamento/agenda.py", rec)

    def test_um_arquivo_de_tudo_derruba_o_recorte(self):
        """O raio só soma: um módulo e um arquivo sem dono juntos = suíte."""
        itens = raio.avaliar(["isocentro/modulos/plano/calculo.py",
                              "requirements.txt"], self.grafo)
        self.assertEqual(raio.nivel_total(itens), TUDO)
        self.assertIsNone(raio.recorte(itens, self.raiz))
        self.assertIn("requirements.txt", raio.relatorio(itens, "HEAD"))

    def test_teste_apagado_nao_entra_no_recorte(self):
        """O lado velho de um renome vinha para o recorte e o unittest
        acusava ModuleNotFoundError sem nada estar quebrado."""
        itens = raio.avaliar(["tests/test_sumiu.py", "tests/test_plano.py"],
                             self.grafo)
        self.assertEqual(raio.recorte(itens, self.raiz), ["tests/test_plano.py"])

    def test_documento_roda_so_o_teste_que_o_le(self):
        self.escrever("tests/test_notas.py", "LER = 'NOTAS.md'\n")
        itens = raio.avaliar(["NOTAS.md"], self.grafo)
        self.assertEqual(raio.nivel_total(itens), NENHUM)
        self.assertEqual(raio.recorte(itens, self.raiz), ["tests/test_notas.py"])


@unittest.skipUnless(shutil.which("git"), "git ausente")
class TestDiff(_Arvore):

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.raiz, check=True,
                       capture_output=True)

    def test_renomeado_aparece_dos_dois_lados_e_o_novo_entra(self):
        """Sem ``--no-renames`` o arquivo velho some do diff, e com ele o
        dono antigo — que pode ser outro módulo."""
        self.git("init", "-q")
        self.git("config", "user.email", "robo@exemplo")
        self.git("config", "user.name", "robo")
        self.git("config", "commit.gpgsign", "false")
        self.escrever("isocentro/papel/velho.py", "x = 1\n" * 20)
        self.escrever("NOTAS.md", "a\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        (self.raiz / "isocentro/dominio").mkdir(parents=True)
        self.git("mv", "isocentro/papel/velho.py", "isocentro/dominio/paralelo.py")
        self.escrever("NOTAS.md", "b\n")
        self.escrever("tools/novo.py", "")
        self.assertEqual(raio.arquivos_do_diff("HEAD", self.raiz),
                         ["NOTAS.md", "isocentro/dominio/paralelo.py",
                          "isocentro/papel/velho.py", "tools/novo.py"])


class TestRepositorioDeVerdade(unittest.TestCase):

    def test_o_dicom_rt_alcanca_o_papel(self):
        """É o caso que motivou a dimensão do papel: o SSD da ficha sai dele."""
        alc = raio.alcanca_papel(raio.montar_grafo(RAIZ))
        self.assertIn("isocentro/dicom/dicom_rt.py", alc)
        self.assertIn("isocentro/papel/rodape.py", alc)


class TestImportNoTestar(unittest.TestCase):

    def test_from_pacote_import_modulo_casa(self):
        """``from isocentro.papel import ficha_pdf`` é como os testes do papel
        importam, e o recorte antigo não os achava."""
        p = testar._padrao_de_import("isocentro.papel.ficha_pdf")
        self.assertTrue(p.search("from isocentro.papel import ficha_pdf as fp\n"))
        self.assertTrue(p.search("    from isocentro.papel import (rodape,\n"
                                 "        ficha_pdf)\n"))
        self.assertTrue(p.search("import isocentro.papel.ficha_pdf\n"))
        self.assertFalse(p.search("from isocentro.papel import rodape\n"))
        self.assertFalse(p.search("from isocentro.papel import ficha_pdf_v2\n"))

    def test_init_do_pacote_se_importa_pelo_pacote(self):
        self.assertEqual(testar._modulo(RAIZ / "isocentro/papel/__init__.py"),
                         "isocentro.papel")

    def test_ferramenta_casa_pelo_nome_solto(self):
        p = testar._padrao_de_import("tools.mapa")
        self.assertTrue(p.search("import mapa  # noqa\n"))
        self.assertFalse(p.search("import mapa_velho\n"))


if __name__ == "__main__":
    unittest.main()
