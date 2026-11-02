"""O app sobe o PostgreSQL local ao abrir (pedido de 29/10/2026).

O que estes testes guardam:

- a estação da clínica, com o banco central em outro servidor, tentando
  subir um PostgreSQL que não é dela;
- um segundo ``pg_ctl start`` disparado com o servidor já no ar;
- o app tentando rodar um ``pg_ctl`` que não existe nesta máquina.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from isocentro.adaptadores.postgres import local


class TestSubir(unittest.TestCase):

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.bin = tmp / "bin"
        self.dados = tmp / "dev"
        self.bin.mkdir()
        self.dados.mkdir()
        (self.bin / "pg_ctl.exe").write_bytes(b"")
        (self.dados / "PG_VERSION").write_text("18", encoding="utf-8")
        self.variaveis = {
            "ISOCENTRO_PG_APP": "host=localhost port=5433 user=postgres",
            "ISOCENTRO_PG_LOCAL_BIN": str(self.bin),
            "ISOCENTRO_PG_LOCAL_DADOS": str(self.dados),
        }

    def _subir(self, no_ar=False):
        ler = lambda nome, padrao="": self.variaveis.get(nome, padrao)  # noqa: E731
        with mock.patch.object(local.ambiente, "ler", ler), \
                mock.patch.object(local, "no_ar", return_value=no_ar), \
                mock.patch.object(local.subprocess, "Popen") as popen:
            feito = local.subir_se_preciso()
        return feito, popen

    def test_fora_e_instalado_sobe_destacado(self):
        feito, popen = self._subir()
        popen.assert_called_once()
        comando = popen.call_args.args[0]
        self.assertEqual(comando[0], str(self.bin / "pg_ctl.exe"))
        self.assertEqual(comando[1:3], ["-D", str(self.dados)])
        self.assertEqual(comando[-1], "start")
        self.assertIn("subindo", feito)
        if local.os.name == "nt":
            # Destacado, o postgres caiu com o Ctrl+C de outro console
            # (0xC000013A, 29/10/2026).
            flags = popen.call_args.kwargs["creationflags"]
            self.assertTrue(flags & local.subprocess.CREATE_NO_WINDOW)
            self.assertFalse(flags & local.subprocess.DETACHED_PROCESS)

    def test_ja_no_ar_nao_dispara_outro(self):
        feito, popen = self._subir(no_ar=True)
        popen.assert_not_called()
        self.assertIn("já no ar", feito)

    def test_banco_central_remoto_nao_e_da_estacao(self):
        self.variaveis["ISOCENTRO_PG_APP"] = "host=srvbanco port=5432"
        feito, popen = self._subir()
        popen.assert_not_called()
        self.assertEqual(feito, "")

    def test_sem_variavel_nada(self):
        del self.variaveis["ISOCENTRO_PG_APP"]
        feito, popen = self._subir()
        popen.assert_not_called()
        self.assertEqual(feito, "")

    def test_sem_servidor_instalado_diz_e_nao_dispara(self):
        (self.bin / "pg_ctl.exe").unlink()
        feito, popen = self._subir()
        popen.assert_not_called()
        self.assertIn("não instalado", feito)

    def test_porta_vem_da_conninfo_com_aspas(self):
        self.assertEqual(local._campos("host='localhost' port=5433")["port"],
                         "5433")


if __name__ == "__main__":
    unittest.main()
