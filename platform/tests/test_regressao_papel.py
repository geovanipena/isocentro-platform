"""A ficha de hoje contra a ficha aprovada (``tools/regressao_papel.py``).

Até 22/10/2026 nenhum teste conferia a ficha INTEIRA: a suíte confere cada
função, e uma mudança no `dominio/` que deslocasse uma dose impressa passava
verde. "Documento impresso muda com aviso" dependia de alguém lembrar de rodar
o `caso.py` e o `comparar_pdf.py` antes e depois.

Quando o papel muda DE PROPÓSITO: `python tools/regressao_papel.py --gravar`,
e o diff do `tests/papel_referencia/*.json` vai no commit — é ele o aviso.

Pulado onde não há o acervo pseudonimizado (`../../dicom-teste/`, fora do
repositório: o TC8 sozinho tem 84 MB), e o pulo DIZ por quê. Na CI, portanto,
este portão não existe; ele vale na estação, no `/pronto`.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import regressao_papel  # noqa: E402


@unittest.skipUnless(regressao_papel.ACERVO.is_dir(),
                     "sem o acervo pseudonimizado dicom-teste/ (CI ou outra estação)")
class PapelIgualAoAprovado(unittest.TestCase):

    def test_as_fichas_dos_casos_de_referencia_nao_mudaram(self):
        diferencas = {nome: linhas
                      for nome, linhas in regressao_papel.conferir().items()
                      if linhas}
        relato = "\n".join(f"{nome}:\n  " + "\n  ".join(linhas[:15])
                           for nome, linhas in diferencas.items())
        self.assertEqual(
            diferencas, {},
            "O PAPEL MUDOU. Se foi de propósito, avisar o usuário do que muda e "
            "rodar `python tools/regressao_papel.py --gravar`:\n" + relato)


class ReferenciaSemData(unittest.TestCase):
    """"Impresso em DD/MM/AAAA" é a única célula que muda sozinha. Sem a troca
    pelo marcador, a referência reprovaria no dia seguinte ao de ser gravada."""

    def test_nenhuma_referencia_guarda_data_de_impressao(self):
        for ref in regressao_papel.REFERENCIAS.glob("*.json"):
            texto = ref.read_text(encoding="utf-8")
            self.assertNotRegex(texto, r"Impresso em \d", ref.name)
