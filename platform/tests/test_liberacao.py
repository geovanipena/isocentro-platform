"""Liberar para impressão o caso que a automação preparou (frente 3, 11/09/2026).

O defeito que esta frente fecha: carregado da pasta TEMPORÁRIA, a Impressão
de sempre gravaria a ficha, o registro e o RTPLAN onde o caso foi carregado —
na temporária, que a automação limpa. O que se testa aqui é o que decide o
destino, sem montar a janela: os métodos são chamados com um ``self`` falso.

Rodar:  python -m unittest tests.test_liberacao -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    from isocentro.interface import gui
    from isocentro.interface.caso import Caso
    from isocentro.interface import simulacao
except Exception:  # noqa: BLE001
    gui = None

J = gui.JanelaPrincipal if gui is not None else None


class _Trocas:
    """Troca atributos de módulo e DEVOLVE as originais — nunca ``del``."""

    def __init__(self):
        self._guardadas = []

    def trocar(self, alvo, nome, valor):
        self._guardadas.append((alvo, nome, getattr(alvo, nome)))
        setattr(alvo, nome, valor)

    def devolver(self):
        for alvo, nome, original in reversed(self._guardadas):
            setattr(alvo, nome, original)


@unittest.skipIf(gui is None, "PySide6 indisponível")
class PastaDoPaciente(unittest.TestCase):
    """Para onde vai a ficha liberada."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.temporaria = base / "temporaria"
        self.curso = self.temporaria / "9000001" / "C1"
        self.curso.mkdir(parents=True)
        self.simulacoes = base / "simulacoes"
        self.cadastro = self.simulacoes / "FULANO_9000001" / "09-2026"
        self.cadastro.mkdir(parents=True)
        self.avisos, self.escolhas, self.alertas = [], [], []
        self.t = _Trocas()
        self.t.trocar(simulacao, "raiz", lambda: str(self.simulacoes))
        self.t.trocar(simulacao, "procurar", lambda nome, reg: "")
        self.t.trocar(gui.ui, "avisar",
                      lambda _p, _t, texto, **_k: self.avisos.append(texto))
        self.t.trocar(gui.ui, "alertar",
                      lambda _p, _t, texto, **_k: self.alertas.append(texto))
        escolhas = self.escolhas
        self.t.trocar(gui, "QFileDialog", SimpleNamespace(
            getExistingDirectory=lambda *_a, **_k: (
                escolhas.pop(0) if escolhas else "")))
        self.janela = SimpleNamespace(caso=Caso(
            origem_temporaria={"instancia": 7, "pasta": str(self.curso),
                               "paciente": "Fulano de Tal",
                               "registro": "9000001"}))

    def tearDown(self):
        self.t.devolver()
        self._tmp.cleanup()

    def _pasta(self):
        return J._pasta_do_paciente_para_liberar(self.janela, {})

    def test_com_cadastro_vai_para_a_pasta_da_simulacao_sem_perguntar(self):
        self.t.trocar(simulacao, "procurar",
                      lambda nome, reg: str(self.cadastro))
        self.assertEqual(self._pasta(), str(self.cadastro))
        self.assertEqual(self.avisos, [])

    def test_sem_cadastro_pergunta_e_nao_cria_nada(self):
        """Uma pasta inventada aqui divergiria do nome que a Capa cadastrar
        depois — e o paciente ficaria com duas."""
        outra = self.simulacoes / "escolhida"
        outra.mkdir()
        self.escolhas.append(str(outra))
        self.assertEqual(self._pasta(), str(outra))
        self.assertIn("não tem cadastro de simulação", self.avisos[0])
        self.assertEqual(sorted(p.name for p in self.simulacoes.iterdir()),
                         ["FULANO_9000001", "escolhida"])

    def test_escolher_a_temporaria_e_recusado(self):
        """Gravada na temporária, a ficha definitiva some na limpeza."""
        fora = self.simulacoes / "fora"
        fora.mkdir()
        self.escolhas += [str(self.curso), str(fora)]
        self.assertEqual(self._pasta(), str(fora))
        self.assertEqual(len(self.alertas), 1)

    def test_desistir_nao_grava(self):
        self.assertEqual(self._pasta(), "")

    def test_raiz_inalcancavel_e_outro_aviso(self):
        """"Sem cadastro" pede cadastrar o paciente; raiz fora de alcance pede
        configurar a estação. Com o mesmo aviso, o físico cadastraria de novo
        um paciente que já está cadastrado."""
        self.t.trocar(simulacao, "raiz",
                      lambda: str(self.simulacoes / "nao-existe"))
        self._pasta()
        self.assertIn("não é alcançada", self.avisos[0])


@unittest.skipIf(gui is None, "PySide6 indisponível")
class DentroDe(unittest.TestCase):

    def test_casos(self):
        self.assertTrue(gui._dentro_de("X:/tmp/9000001/C1", "X:/tmp"))
        self.assertTrue(gui._dentro_de("X:/tmp", "X:/tmp"))
        self.assertTrue(gui._dentro_de("x:/TMP/a", "X:/tmp"))   # Windows
        self.assertFalse(gui._dentro_de("X:/tmpx/a", "X:/tmp"))
        self.assertFalse(gui._dentro_de("Y:/tmp/a", "X:/tmp"))


@unittest.skipIf(gui is None, "PySide6 indisponível")
class AbrirDocumentacao(unittest.TestCase):
    """O clique no ``● PRONTA`` abre o caso e marca a origem."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.curso = str(Path(self._tmp.name) / "9000001" / "C1")
        os.makedirs(self.curso)
        self.status, self.liberacoes = [], []
        self.janela = SimpleNamespace(
            caso=Caso(), _papel="fisico",
            fichinha=SimpleNamespace(
                mostrar_status=lambda m, erro=False: self.status.append(
                    (m, erro)),
                definir_caminho=lambda c: None,
                definir_liberacao=self.liberacoes.append))
        self.janela._fichinha_gerar = lambda c: setattr(
            self.janela.caso, "pasta_carregada", c)

    def tearDown(self):
        self._tmp.cleanup()

    def _entrada(self, pasta):
        return {"instancia": 7, "paciente": "Fulano de Tal",
                "registro": "9000001",
                "automacao": {"estado": "pronta", "pasta": pasta}}

    def test_carga_que_comecou_marca_a_origem_e_acende_a_liberacao(self):
        J._fichinha_abrir_documentacao(self.janela, self._entrada(self.curso))
        self.assertEqual(self.janela.caso.origem_temporaria["instancia"], 7)
        self.assertEqual(self.liberacoes, [{"permitido": True}])

    def test_medico_abre_mas_nao_libera(self):
        """Conferir o caso é de quem abre a Fichinha; liberar é do físico."""
        self.janela._papel = "medico"
        J._fichinha_abrir_documentacao(self.janela, self._entrada(self.curso))
        self.assertEqual(self.liberacoes, [{"permitido": False}])

    def test_pasta_que_nao_se_alcanca_diz_e_nao_carrega(self):
        J._fichinha_abrir_documentacao(
            self.janela, self._entrada(self.curso + "-sumiu"))
        self.assertIsNone(self.janela.caso.pasta_carregada)
        self.assertTrue(self.status[0][1])

    def test_carga_que_nao_comecou_nao_marca_origem(self):
        """Com outra carga em curso o ``_fichinha_gerar`` só avisa. Marcada
        mesmo assim, a origem grudaria no caso que JÁ estava na bancada, e a
        Impressão dele viraria a liberação de outro."""
        self.janela._fichinha_gerar = lambda c: None
        J._fichinha_abrir_documentacao(self.janela, self._entrada(self.curso))
        self.assertIsNone(self.janela.caso.origem_temporaria)
        self.assertEqual(self.liberacoes, [])


if __name__ == "__main__":
    unittest.main()
