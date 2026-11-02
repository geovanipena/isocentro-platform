"""Checklist Pré-Tratamento gravado — o que a Ficha Virtual consulta.

O checklist continua saindo impresso e sendo assinado na contracapa. O que este
módulo guarda é a resposta a "aquele paciente já passou pela conferência?",
para quem consulta de outra estação e sem a folha na mão.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.interface import checklist  # noqa: E402


class _ComArquivoProprio(unittest.TestCase):
    """Cada teste com o seu JSON: o de verdade é COMPARTILHADO pelo serviço."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self._antes = os.environ.get("ISOCENTRO_CHECKLIST")
        os.environ["ISOCENTRO_CHECKLIST"] = self.d
        self.addCleanup(self._repor)

    def _repor(self):
        if self._antes is None:
            os.environ.pop("ISOCENTRO_CHECKLIST", None)
        else:
            os.environ["ISOCENTRO_CHECKLIST"] = self._antes


class TestItens(unittest.TestCase):

    def test_os_itens_sao_os_do_PAPEL_e_nao_uma_copia(self):
        """Duas listas divergem na primeira vez que alguém mexer no papel.

        Um checklist de tela que não é o da contracapa passa a atestar coisa
        diferente da que foi assinada — e a assinatura é o que a auditoria
        procura.
        """
        from isocentro.papel import capa_pdf
        self.assertIs(checklist.ITENS, capa_pdf.CHECKLIST_ITENS)
        self.assertIs(checklist.MARCAS, capa_pdf.CHECKLIST_COLUNAS)


class TestGravacao(_ComArquivoProprio):

    def test_marca_guarda_QUEM_e_QUANDO(self):
        """Conferência anônima não serve: "quem conferiu a lateralidade" é
        justamente a pergunta que se faz quando algo deu errado."""
        m = checklist.marcar("1X", 3, checklist.ITENS[0], "C", "ivone")
        dado = m[checklist.ITENS[0]]
        self.assertEqual(dado["marca"], "C")
        self.assertEqual(dado["por"], "ivone")
        self.assertTrue(dado["em"])

    def test_marca_vazia_DESMARCA(self):
        """É como se desfaz um clique errado. Sem isso, a única saída seria
        deixar gravada uma conferência que ninguém quis fazer."""
        checklist.marcar("1X", 3, checklist.ITENS[0], "C", "ivone")
        m = checklist.marcar("1X", 3, checklist.ITENS[0], "", "ivone")
        self.assertNotIn(checklist.ITENS[0], m)

    def test_curso_diferente_e_conferencia_DIFERENTE(self):
        """Um por CURSO: replanejamento pede conferência nova.

        Preso ao paciente, um retratamento dois anos depois abriria já marcado
        — e ninguém reconfere o que a tela diz que está conferido.
        """
        checklist.marcar("1X", 1, checklist.ITENS[0], "C", "ivone")
        self.assertEqual(checklist.andamento(checklist.ler("1X", 1))[0], 1)
        self.assertEqual(checklist.andamento(checklist.ler("1X", 2))[0], 0)

    def test_sem_curso_nao_grava(self):
        """Checklist sem curso não tem a que se prender, e gravá-lo juntaria
        numa entrada só conferências de tratamentos diferentes."""
        m = checklist.marcar("1X", None, checklist.ITENS[0], "C", "ivone")
        self.assertEqual(m, {})
        self.assertEqual(checklist.chave("1X", None), "")

    def test_marca_desconhecida_e_ignorada_sem_derrubar(self):
        """Só pode vir de erro de programação — e levantar aqui derrubaria a
        janela no meio de uma conferência já feita pela metade."""
        m = checklist.marcar("1X", 1, checklist.ITENS[0], "XX", "ivone")
        self.assertEqual(m, {})

    def test_item_fora_da_lista_do_papel_nao_entra(self):
        m = checklist.marcar("1X", 1, "Item que não existe", "C", "ivone")
        self.assertEqual(m, {})

    def test_arquivo_corrompido_nao_derruba_a_aba(self):
        """``_carregar`` cai para "nenhuma conferência" — o que não pode é a
        exceção subir e levar junto a tela inteira do paciente."""
        checklist.caminho().write_text("{lixo", encoding="utf-8")
        self.assertEqual(checklist.ler("1X", 1), {})


class TestAndamento(_ComArquivoProprio):

    def _marcar_todos(self, marca="C"):
        for i in checklist.ITENS:
            m = checklist.marcar("1X", 1, i, marca, "ivone")
        return m

    def test_nao_conforme_CONTA_como_respondido(self):
        """Quem marcou "não conforme" OLHOU. Tratar isso como pendência faria
        o cartão pedir uma conferência que já foi feita — e aviso que aparece
        sem motivo deixa de ser lido."""
        m = self._marcar_todos("N/C")
        self.assertEqual(checklist.andamento(m), (6, 6))
        self.assertTrue(checklist.completo(m))

    def test_divergencia_aparece_mesmo_com_a_lista_COMPLETA(self):
        """Seis de seis com um "N/C" no meio é uma conferência completa e um
        paciente que não pode subir na mesa. Dizer "conferido" ali seria a tela
        dando um aval que a própria conferência negou."""
        self._marcar_todos("C")
        m = checklist.marcar("1X", 1, checklist.ITENS[2], "N/C", "ivone")
        self.assertTrue(checklist.completo(m))
        self.assertEqual(checklist.divergencias(m), [checklist.ITENS[2]])

    def test_corrigido_tira_a_divergencia(self):
        """"Cor." é o item que estava errado e foi resolvido — deixá-lo na
        lista de divergências manteria um alarme sobre coisa já consertada."""
        self._marcar_todos("C")
        checklist.marcar("1X", 1, checklist.ITENS[2], "N/C", "ivone")
        m = checklist.marcar("1X", 1, checklist.ITENS[2], "Cor.", "ivone")
        self.assertEqual(checklist.divergencias(m), [])


if __name__ == "__main__":
    unittest.main()
