"""Autenticação: hash, criação/verificação, papéis e seed do admin.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import auth  # noqa: E402


class TestAuth(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.mkdtemp()
        os.environ["ISOCENTRO_USERS_DIR"] = self._d

    def tearDown(self):
        os.environ.pop("ISOCENTRO_USERS_DIR", None)

    def test_criar_e_verificar(self):
        auth.criar("joao", "João Silva", "s3nh@", papel="fisico")
        u = auth.verificar("joao", "s3nh@")
        self.assertIsNotNone(u)
        self.assertEqual(u["papel"], "fisico")
        self.assertEqual(u["nome"], "João Silva")

    def test_senha_errada(self):
        auth.criar("joao", "J", "certa")
        self.assertIsNone(auth.verificar("joao", "errada"))

    def test_usuario_case_insensitive(self):
        auth.criar("Joao", "J", "x")
        self.assertIsNotNone(auth.verificar("JOAO", "x"))

    def test_nao_guarda_senha_em_texto(self):
        auth.criar("joao", "J", "segredo123")
        conteudo = Path(auth.caminho_usuarios()).read_text(encoding="utf-8")
        self.assertNotIn("segredo123", conteudo)
        self.assertIn("salt", conteudo)
        self.assertIn("hash", conteudo)

    def test_duplicado_levanta(self):
        auth.criar("joao", "J", "x")
        with self.assertRaises(ValueError):
            auth.criar("joao", "J2", "y")

    def test_inativo_nao_loga(self):
        auth.criar("joao", "J", "x")
        auth.definir_ativo("joao", False)
        self.assertIsNone(auth.verificar("joao", "x"))

    def test_redefinir_senha(self):
        auth.criar("joao", "J", "antiga")
        auth.redefinir_senha("joao", "nova", trocar_senha=True)
        self.assertIsNone(auth.verificar("joao", "antiga"))
        u = auth.verificar("joao", "nova")
        self.assertTrue(u["trocar_senha"])

    def test_remover(self):
        auth.criar("joao", "J", "x")
        auth.remover("joao")
        self.assertFalse(auth.existe("joao"))

    def test_papel_invalido(self):
        with self.assertRaises(ValueError):
            auth.criar("x", "X", "y", papel="root")

    def test_seed_admin(self):
        self.assertFalse(auth.ha_admin_ativo())
        self.assertTrue(auth.semear_admin_se_vazio())
        u = auth.verificar("admin", "admin")
        self.assertIsNotNone(u)
        self.assertEqual(u["papel"], "admin")
        self.assertTrue(u["trocar_senha"])       # força troca no 1º login
        self.assertFalse(auth.semear_admin_se_vazio())  # idempotente


if __name__ == "__main__":
    unittest.main()
