"""A Alta de uma ficha recarregada do JSON sai com as imagens do registro.

Relatado em 18/09/2026: recarregar o registro, mudar qualquer coisa e gerar de
novo — a ficha saía certa, e a Alta ao lado dela saía com "TC não carregada —
importe a série completa." e "DVH requer RT Struct + RT Dose." no lugar das
imagens. Com UM plano, a ``salvar_alta`` chamava ``gerar_alta(dados,
recursos)``, que desenha da TC; recarregado do JSON não há TC. A ficha do
mesmo clique usava os PNGs do registro — a Alta nunca os recebeu.

Não era da R-06: o ``_salvar_alta`` de antes dos cortes tinha a mesma lógica.
O multi-plano nunca teve o defeito, porque lá os PNGs vão por plano
(``cortes_salvo``/``dvh_salvo``).
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from isocentro.interface.controle_ficha import ControleFicha  # noqa: E402

_DADOS = {"pac_nome": "PACIENTE TESTE", "pac_registro": "9000001",
          "maquina": "600CD"}


def _png(cor: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), cor).save(buf, "PNG")
    return buf.getvalue()


def _janela_falsa():
    return types.SimpleNamespace(
        caso=types.SimpleNamespace(agendamento=None),
        status=types.SimpleNamespace(showMessage=lambda _m: None))


class TestAltaArquivada(unittest.TestCase):

    def _gerar(self, **kw) -> "PdfReader":
        with tempfile.TemporaryDirectory() as pasta:
            ControleFicha(_janela_falsa()).salvar_alta(
                _DADOS, {}, None, False, "individual",
                os.path.join(pasta, "FICHA_x.pdf"), "x", "_v2", "18-09-2026",
                **kw)
            altas = [f for f in os.listdir(pasta) if f.startswith("ALTA_")]
            self.assertEqual(len(altas), 1, "a Alta não foi gravada")
            with open(os.path.join(pasta, altas[0]), "rb") as f:
                return PdfReader(io.BytesIO(f.read()))

    def test_recarregada_leva_os_cortes_e_o_dvh_do_registro(self):
        pg = self._gerar(arquivado=True, cortes_png=_png("navy"),
                         dvh_png=_png("teal")).pages[0]
        texto = pg.extract_text()
        self.assertNotIn("TC não carregada", texto)
        self.assertNotIn("DVH requer", texto)
        # Logo + cortes + DVH. Antes era só o logo.
        self.assertGreaterEqual(len(pg.images), 3)

    def test_sem_png_no_registro_diz_que_falta_e_nao_pede_TC(self):
        """Registro sem PNG (versão antiga, arquivo perdido): a Alta diz que a
        imagem não está disponível. "Importe a série completa" seria mandar o
        usuário atrás de uma TC que o fluxo recarregado nunca usa."""
        texto = self._gerar(arquivado=True).pages[0].extract_text()
        self.assertIn("Imagem de cortes não disponível", texto)
        self.assertIn("DVH não disponível", texto)
        self.assertNotIn("TC não carregada", texto)

    def test_gerando_do_dicom_continua_no_caminho_de_sempre(self):
        """Controle: sem ``arquivado`` nada muda — é o ``gerar_alta`` que
        desenha da TC, e sem TC ele diz isso."""
        texto = self._gerar().pages[0].extract_text()
        self.assertIn("TC não carregada", texto)


if __name__ == "__main__":
    unittest.main()
