"""A ferramenta que desce seções do `NOTAS.md` (``tools/notas.py``).

Ela roda sozinha na abertura da sessão, sem ninguém olhar — então os modos de
falhar que importam são os silenciosos:

- **perder texto**: descer é mover byte a byte. Uma seção que some do
  `NOTAS.md` e não aparece inteira no `notas/AAAA-MM.md` é história apagada;
- **descer o que está vivo**: a primeira seção é o checkpoint de agora e nunca
  sai; seção sem data não é adivinhada;
- **sumir com o aberto**: seção que se declara EM ANDAMENTO desce, mas ganha
  linha em "O que está aberto" — sair da frente não pode ser sair da vista.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import notas  # noqa: E402

HOJE = date(2026, 10, 22)

CABECALHO = "# Notas de trabalho\n\nCabeçalho do arquivo.\n\n---\n\n"
ABERTO = (
    "## O que está aberto\n\n"
    "As seções que se declaram abertas.\n\n"
    "- 02/09 — [Antiga](notas/2026-09.md)\n\n"
    "---\n\n"
    "## Índice do que já foi (1 seções)\n\n"
    "Uma linha por seção.\n\n"
    "### `notas/2026-09.md` — setembro (1 seções)\n\n"
    "- 02/09 — [Antiga](notas/2026-09.md)\n"
)


def _secao(titulo: str, linhas: int = 3) -> str:
    return f"## {titulo}\n\n" + "".join(f"linha {i} de {titulo}\n" for i in range(linhas)) + "\n---\n\n"


class TestDescer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        (self.raiz / "notas").mkdir()
        (self.raiz / "notas" / "2026-09.md").write_bytes(
            "# Notas — setembro\r\n\r\nCongelada.\r\n\r\n---\r\n\r\n## Antiga — 02/09/2026\r\n\r\ntexto\r\n".encode())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _gravar(self, *secoes: str) -> None:
        (self.raiz / "NOTAS.md").write_bytes((CABECALHO + "".join(secoes) + ABERTO).encode())

    def _ler(self, rel: str) -> str:
        return (self.raiz / rel).read_bytes().decode()

    def test_desce_a_vencida_e_fica_a_recente(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Recente — 15/10/2026"),
                     _secao("Vencida — 01/10/2026"))
        relato = notas.descer(self.raiz, alvo=1000, hoje=HOJE)
        self.assertEqual(len(relato), 1)
        texto = self._ler("NOTAS.md")
        self.assertIn("## Recente — 15/10/2026", texto)
        self.assertNotIn("## Vencida", texto)
        self.assertIn(_secao("Vencida — 01/10/2026"), self._ler("notas/2026-10.md"))
        self.assertIn("- 01/10 — [Vencida](notas/2026-10.md)", texto)

    def test_a_primeira_secao_nunca_desce(self) -> None:
        self._gravar(_secao("Velha mas viva — 01/08/2026"), _secao("Outra — 02/08/2026"))
        notas.descer(self.raiz, alvo=1, hoje=HOJE)
        self.assertIn("## Velha mas viva", self._ler("NOTAS.md"))

    def test_sem_data_nao_desce(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Sem data nenhuma"))
        notas.descer(self.raiz, alvo=1, hoje=HOJE)
        self.assertIn("## Sem data nenhuma", self._ler("NOTAS.md"))

    def test_acima_do_alvo_desce_a_mais_antiga_primeiro(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026", 50), _secao("Meio — 18/10/2026", 50),
                     _secao("Velha — 17/10/2026", 50))
        relato = notas.descer(self.raiz, alvo=150, hoje=HOJE)
        self.assertEqual([r.split(" ", 1)[0] for r in relato], ["17/10"])
        self.assertIn("## Meio", self._ler("NOTAS.md"))

    def test_aberta_desce_e_vai_para_o_que_esta_aberto(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("EM ANDAMENTO: frente — 01/10/2026"))
        notas.descer(self.raiz, alvo=1000, hoje=HOJE)
        aberto = self._ler("NOTAS.md").split("## Índice")[0]
        self.assertIn("[EM ANDAMENTO: frente](notas/2026-10.md) — desceu sozinha em 22/10/2026", aberto)
        self.assertIn("- 02/09 — [Antiga]", aberto)

    def test_mes_existente_soma_no_indice_e_respeita_crlf(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Setembro — 10/09/2026"))
        notas.descer(self.raiz, alvo=1000, hoje=HOJE)
        texto = self._ler("NOTAS.md")
        self.assertIn("### `notas/2026-09.md` — setembro (2 seções)\n\n- 10/09 — [Setembro]", texto)
        self.assertIn("## Índice do que já foi (2 seções)", texto)
        arq = self._ler("notas/2026-09.md")
        self.assertNotIn("\n\n", arq.replace("\r\n", ""))   # nenhuma quebra LF solta
        self.assertLess(arq.index("## Setembro"), arq.index("## Antiga"))

    def test_mes_novo_entra_antes_dos_antigos_no_indice(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Outubro — 01/10/2026"))
        notas.descer(self.raiz, alvo=1000, hoje=HOJE)
        texto = self._ler("NOTAS.md")
        self.assertLess(texto.index("### `notas/2026-10.md` — outubro (1 seções)"),
                        texto.index("### `notas/2026-09.md`"))

    def test_preserva_crlf_do_notas(self) -> None:
        texto = (CABECALHO + _secao("Viva — 21/10/2026") + _secao("Vencida — 01/10/2026") + ABERTO)
        (self.raiz / "NOTAS.md").write_bytes(texto.replace("\n", "\r\n").encode())
        notas.descer(self.raiz, alvo=1000, hoje=HOJE)
        bruto = self._ler("NOTAS.md")
        self.assertNotIn("\n", bruto.replace("\r\n", ""))

    def test_simular_nao_grava(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Vencida — 01/10/2026"))
        antes = self._ler("NOTAS.md")
        self.assertEqual(len(notas.descer(self.raiz, alvo=1000, hoje=HOJE, simular=True)), 1)
        self.assertEqual(self._ler("NOTAS.md"), antes)
        self.assertFalse((self.raiz / "notas" / "2026-10.md").exists())

    def test_nada_a_descer(self) -> None:
        self._gravar(_secao("Viva — 21/10/2026"), _secao("Recente — 20/10/2026"))
        self.assertEqual(notas.descer(self.raiz, alvo=1000, hoje=HOJE), [])


if __name__ == "__main__":
    unittest.main()
