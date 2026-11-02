"""O ``constraints.txt`` e quem o gera (``tools/gerar_constraints.py``, frente R-56).

O arquivo fixa as dependências das dependências. Se ele envelhecer — alguém sobe
uma versão no ``requirements.txt`` e esquece de regerar —, o CI instala uma
coisa e a estação outra, e ninguém percebe até um PDF sair diferente. Estes
testes rodam no ambiente instalado com ``-r requirements.txt -c constraints.txt``
(o do CI e o da estação), onde regerar tem de dar exatamente o que está gravado.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

from packaging.requirements import Requirement  # noqa: E402
from packaging.utils import canonicalize_name  # noqa: E402

import gerar_constraints as gc  # noqa: E402


def _fixados(linhas: list[str]) -> dict[str, str]:
    out = {}
    for linha in linhas:
        linha = linha.split("#", 1)[0].strip()
        if linha:
            nome, versao = linha.split("==")
            out[canonicalize_name(nome)] = versao
    return out


class TestConstraints(unittest.TestCase):

    def test_ambiente_tem_os_diretos_na_versao_fixada(self):
        self.assertEqual(gc.conferir_diretos(gc._diretos()), "")

    def test_constraints_gravado_bate_com_o_ambiente(self):
        """Regerar agora tem de dar o arquivo que está no repositório."""
        gravado = gc.CONSTRAINTS.read_text(encoding="utf-8")
        self.assertEqual(gravado, gc.texto(gc.pacotes(gc._diretos())),
                         "constraints.txt desatualizado: rode tools/gerar_constraints.py")

    def test_todo_direto_esta_no_constraints_na_mesma_versao(self):
        fixados = _fixados(gc.CONSTRAINTS.read_text(encoding="utf-8").splitlines())
        for req in gc._diretos():
            versao = next(iter(req.specifier)).version
            self.assertEqual(fixados.get(canonicalize_name(req.name)), versao, req.name)

    def test_so_entra_o_que_o_requirements_puxa(self):
        """Ferramenta da estação (ruff, pyinstaller) não vira dependência do app."""
        fixados = _fixados(gc.CONSTRAINTS.read_text(encoding="utf-8").splitlines())
        for fora in ("ruff", "pyinstaller", "pip", "setuptools"):
            self.assertNotIn(fora, fixados)

    def test_pacote_ausente_e_dito_pelo_nome(self):
        erro = gc.conferir_diretos([Requirement("pacote-que-nao-existe==1.0")])
        self.assertIn("pacote-que-nao-existe", erro)

    def test_versao_diferente_da_fixada_e_dita(self):
        erro = gc.conferir_diretos([Requirement("packaging==0.0.1")])
        self.assertIn("packaging", erro)
        self.assertIn("0.0.1", erro)


if __name__ == "__main__":
    unittest.main()
