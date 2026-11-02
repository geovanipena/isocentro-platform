"""A cópia redundante do registro do paciente (``dados/backup.py``).

É a segunda cópia do ``.zip`` do paciente: se a pasta do paciente se perde, é a
que sobra. Dois jeitos de ela falhar em silêncio: ficar truncada (cópia
interrompida no meio) ou ir para um lugar que ninguém procura. E o contrato do
lado oposto: uma falha aqui nunca pode travar a geração da ficha.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import ambiente, backup  # noqa: E402

VARS = ("ISOCENTRO_BACKUP_DIR", "ISOCENTRO_PASTA_APP")


class TestBackup(unittest.TestCase):

    def setUp(self):
        self._antes = {n: os.environ.pop(n, None) for v in VARS for n in ambiente.nomes(v)}
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.zip = self.tmp / "paciente" / "REG123_FULANO.zip"
        self.zip.parent.mkdir()
        self.zip.write_bytes(b"conteudo do registro")

    def tearDown(self):
        for nome in self._antes:
            os.environ.pop(nome, None)
        for nome, valor in self._antes.items():
            if valor is not None:
                os.environ[nome] = valor
        self._tmp.cleanup()

    def test_copia_para_o_diretorio_configurado(self):
        os.environ["ISOCENTRO_BACKUP_DIR"] = str(self.tmp / "rede")
        destino = backup.copiar(str(self.zip))
        self.assertEqual(Path(destino), self.tmp / "rede" / self.zip.name)
        self.assertEqual(Path(destino).read_bytes(), b"conteudo do registro")

    def test_sem_variavel_vai_para_backup_registros_na_pasta_do_app(self):
        """Na estação de desenvolvimento a pasta do app é a da ISOCENTRO_PASTA_APP (R-57)."""
        os.environ["ISOCENTRO_PASTA_APP"] = str(self.tmp / "estacao")
        self.assertEqual(backup.dir_backup(), self.tmp / "estacao" / "backup_registros")
        destino = backup.copiar(str(self.zip))
        self.assertEqual(Path(destino).parent, self.tmp / "estacao" / "backup_registros")

    def test_sobrescreve_a_copia_antiga_inteira_e_nao_deixa_temporario(self):
        os.environ["ISOCENTRO_BACKUP_DIR"] = str(self.tmp / "rede")
        backup.copiar(str(self.zip))
        self.zip.write_bytes(b"versao nova")
        destino = Path(backup.copiar(str(self.zip)))
        self.assertEqual(destino.read_bytes(), b"versao nova")
        self.assertEqual([p.name for p in destino.parent.iterdir()], [self.zip.name])

    def test_registro_inexistente_devolve_none(self):
        os.environ["ISOCENTRO_BACKUP_DIR"] = str(self.tmp / "rede")
        self.assertIsNone(backup.copiar(str(self.tmp / "nao_existe.zip")))

    def test_falha_no_destino_nao_levanta_erro(self):
        """Destino impossível (um arquivo no lugar da pasta): devolve None, a ficha segue."""
        bloqueio = self.tmp / "rede"
        bloqueio.write_text("sou um arquivo")
        os.environ["ISOCENTRO_BACKUP_DIR"] = str(bloqueio)
        self.assertIsNone(backup.copiar(str(self.zip)))
        self.assertEqual(bloqueio.read_text(), "sou um arquivo")


if __name__ == "__main__":
    unittest.main()
