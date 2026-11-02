"""A ferramenta que mede a diferença entre dois PDF (``tools/comparar_pdf.py``).

O que ela existe para pegar é o que o olho não pega numa folha cheia: um valor
que trocou dentro da célula e uma célula que andou poucos pontos. Os testes
abaixo montam PDF de verdade (reportlab, o mesmo que desenha a ficha) e conferem
que cada caso cai na categoria certa — em especial que célula que ANDOU não é
relatada como uma que sumiu mais uma que surgiu, que era o diagnóstico errado
que a comparação a olho dava.
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import comparar_pdf  # noqa: E402


def _pdf(caminho: Path, celulas, tamanho=(595, 842)) -> None:
    """Escreve um PDF de uma página com cada texto na coordenada pedida."""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(caminho), pagesize=tamanho)
    for x, y, texto in celulas:
        c.drawString(x, y, texto)
    c.showPage()
    c.save()


class TestComparar(unittest.TestCase):

    def setUp(self):
        if comparar_pdf.fitz is None:
            self.skipTest("PyMuPDF não está nesta estação")
        self.pasta = Path(tempfile.mkdtemp(prefix="comparar_pdf_"))
        self.base = [(72, 700, "SSD 92,3"), (72, 680, "Gantry 180"),
                     (300, 700, "40,05 Gy / 15 fr")]

    def tearDown(self):
        for arq in self.pasta.glob("*.pdf"):
            arq.unlink()
        self.pasta.rmdir()

    def _comparar(self, depois_celulas):
        a, b = self.pasta / "antes.pdf", self.pasta / "depois.pdf"
        _pdf(a, self.base)
        _pdf(b, depois_celulas)
        antes, _ = comparar_pdf._celulas(a, None)
        depois, _ = comparar_pdf._celulas(b, None)
        return comparar_pdf.comparar(antes, depois, tol=1.0)

    def test_pdf_identico_nao_gera_linha_nenhuma(self):
        """Célula igual não pode virar saída: o custo da ferramenta é o texto."""
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(self.base)
        self.assertEqual(iguais, 3)
        self.assertEqual((mudou, moveu, sumiu, surgiu), ([], [], [], []))

    def test_valor_trocado_no_mesmo_lugar_e_MUDOU(self):
        """92,3 → 91,8 no meio da tabela é o erro que a conferência a olho passa."""
        alterado = [(72, 700, "SSD 91,8"), *self.base[1:]]
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(alterado)
        self.assertEqual(iguais, 2)
        self.assertEqual(len(mudou), 1)
        self.assertEqual((moveu, sumiu, surgiu), ([], [], []))
        antes, depois = mudou[0]
        self.assertEqual(antes.texto, "SSD 92,3")
        self.assertEqual(depois.texto, "SSD 91,8")

    def test_celula_deslocada_e_MOVEU_e_nao_sumiu_mais_surgiu(self):
        """O diagnóstico errado que motivou as quatro passadas em ordem."""
        deslocado = [self.base[0], (72, 668, "Gantry 180"), self.base[2]]
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(deslocado)
        self.assertEqual(iguais, 2)
        self.assertEqual(len(moveu), 1)
        self.assertEqual((mudou, sumiu, surgiu), ([], [], []))
        antes, depois = moveu[0]
        # y do PyMuPDF cresce para BAIXO, e o do reportlab para cima: subir 12
        # pontos no desenho aparece como +12 aqui. É a leitura certa da página.
        self.assertAlmostEqual(depois.y - antes.y, 12.0, delta=0.5)

    def test_celula_repetida_casa_com_a_mais_proxima(self):
        """Duas células com o mesmo texto: casar pela primeira relataria a outra."""
        self.base = [(72, 700, "0,0"), (72, 600, "0,0")]
        movido = [(72, 700, "0,0"), (90, 600, "0,0")]
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(movido)
        self.assertEqual(iguais, 1)
        self.assertEqual(len(moveu), 1)
        self.assertEqual((mudou, sumiu, surgiu), ([], [], []))
        antes, depois = moveu[0]
        self.assertAlmostEqual(depois.x - antes.x, 18.0, delta=0.5)
        # A célula que andou é a de BAIXO. O y do PyMuPDF é o topo do desenho e
        # cresce para baixo, então a de cima (reportlab y=700) fica perto de 142
        # e esta, perto de 229 — o que separa as duas homônimas.
        self.assertGreater(antes.y, 200)

    def test_celula_que_saiu_e_que_entrou(self):
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(
            [self.base[0], self.base[1], (300, 660, "Observações do caso")])
        self.assertEqual(iguais, 2)
        self.assertEqual(len(sumiu), 1)
        self.assertEqual(len(surgiu), 1)
        self.assertEqual((mudou, moveu), ([], []))

    def test_tolerancia_absorve_o_ruido_de_arredondamento(self):
        """Meio ponto não é mudança de layout — seria só barulho na saída."""
        quase = [(72.4, 700.3, "SSD 92,3"), *self.base[1:]]
        iguais, mudou, moveu, sumiu, surgiu = self._comparar(quase)
        self.assertEqual(iguais, 3)
        self.assertEqual((mudou, moveu, sumiu, surgiu), ([], [], [], []))


class TestSaida(unittest.TestCase):
    """A linha de comando: o código de saída é o que serve dentro de script."""

    def setUp(self):
        if comparar_pdf.fitz is None:
            self.skipTest("PyMuPDF não está nesta estação")
        self.pasta = Path(tempfile.mkdtemp(prefix="comparar_pdf_"))
        self.a = self.pasta / "a.pdf"
        self.b = self.pasta / "b.pdf"

    def tearDown(self):
        for arq in self.pasta.glob("*.pdf"):
            arq.unlink()
        self.pasta.rmdir()

    def _rodar(self, *args):
        saida = io.StringIO()
        antigo, sys.stdout = sys.stdout, saida
        try:
            codigo = comparar_pdf.main([str(self.a), str(self.b), *args])
        finally:
            sys.stdout = antigo
        return codigo, saida.getvalue()

    def test_iguais_devolve_zero(self):
        _pdf(self.a, [(72, 700, "igual")])
        _pdf(self.b, [(72, 700, "igual")])
        codigo, texto = self._rodar()
        self.assertEqual(codigo, 0)
        self.assertIn("mesma coisa", texto)

    def test_diferentes_devolvem_um_e_listam_a_celula(self):
        _pdf(self.a, [(72, 700, "SSD 92,3")])
        _pdf(self.b, [(72, 700, "SSD 91,8")])
        codigo, texto = self._rodar()
        self.assertEqual(codigo, 1)
        self.assertIn("MUDOU", texto)
        self.assertIn("91,8", texto)

    def test_arquivo_que_nao_existe_nao_e_diferenca(self):
        """Código 2, não 1: script que confia no 1 leria falta de arquivo como mudança."""
        _pdf(self.a, [(72, 700, "só um")])
        codigo, _texto = self._rodar()
        self.assertEqual(codigo, 2)

    def test_pagina_a_mais_avisa_em_primeiro_lugar(self):
        """Documento com outra contagem de páginas: sem o aviso, a lista mente."""
        _pdf(self.a, [(72, 700, "x")])
        _pdf(self.b, [(72, 700, "x")], tamanho=(842, 595))
        _codigo, texto = self._rodar()
        self.assertIn("ATENÇÃO", texto)


if __name__ == "__main__":
    unittest.main()
