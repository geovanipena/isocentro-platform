"""Preferência de tela é da PESSOA, não da máquina.

O Grupo Médico ia para o ``QSettings`` (``HKEY_CURRENT_USER``, por estação):
o médico montava o grupo na sala de comando e, no consultório, encontrava
"Todos os médicos" de novo. E duas pessoas que dividem a mesma estação dividiam
a mesma escolha — quem entrasse depois via a agenda montada pelo colega.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import auth  # noqa: E402
from isocentro.dados import preferencias  # noqa: E402

CHAVE = "medicos_do_painel"


class _PastaLimpa(unittest.TestCase):
    """Aponta os usuários (e, com eles, as preferências) para pasta descartável."""

    def setUp(self):
        self._d = tempfile.mkdtemp(prefix="preferencias_")
        self._antes = os.environ.get("ISOCENTRO_USERS_DIR")
        os.environ["ISOCENTRO_USERS_DIR"] = self._d

    def tearDown(self):
        if self._antes is None:
            os.environ.pop("ISOCENTRO_USERS_DIR", None)
        else:
            os.environ["ISOCENTRO_USERS_DIR"] = self._antes
        shutil.rmtree(self._d, ignore_errors=True)


class TestPreferencias(_PastaLimpa):

    def test_grava_e_le(self):
        preferencias.gravar("geovani.pena", CHAVE, ["Dr. A", "Dr. B"])
        self.assertEqual(preferencias.ler("geovani.pena", CHAVE),
                         ["Dr. A", "Dr. B"])

    def test_aceita_o_dicionario_do_login(self):
        """Quem chama tem o usuário do ``auth.verificar``, não o nome solto."""
        u = {"usuario": "Geovani.Pena", "nome": "Geovani", "papel": "fisico"}
        preferencias.gravar(u, CHAVE, ["Dr. A"])
        self.assertEqual(preferencias.ler("geovani.pena", CHAVE), ["Dr. A"])

    def test_uma_pessoa_nao_ve_a_escolha_da_outra(self):
        """O caso que fez a preferência sair do QSettings da estação."""
        preferencias.gravar("medico.a", CHAVE, ["Dr. A"])
        preferencias.gravar("medico.b", CHAVE, ["Dr. B"])
        self.assertEqual(preferencias.ler("medico.a", CHAVE), ["Dr. A"])
        self.assertEqual(preferencias.ler("medico.b", CHAVE), ["Dr. B"])

    def test_sem_escolha_devolve_o_padrao(self):
        self.assertIsNone(preferencias.ler("ninguem", CHAVE))
        self.assertEqual(preferencias.ler("ninguem", CHAVE, []), [])

    def test_lista_vazia_e_uma_escolha(self):
        """Lista vazia GRAVADA volta vazia, e não como "nunca escolheu".

        Quem chama pode querer distinguir as duas coisas — desmarcar todos os
        médicos é decisão, e o padrão só deveria entrar quando ninguém decidiu.
        Guardar a lista vazia como ausência tiraria essa escolha de quem lê.
        """
        preferencias.gravar("geovani.pena", CHAVE, [])
        self.assertEqual(preferencias.ler("geovani.pena", CHAVE, ["x"]), [])

    def test_mora_ao_lado_dos_usuarios(self):
        """Os dois falam do mesmo usuário: apontar a rede leva os dois juntos."""
        self.assertEqual(preferencias.caminho().parent,
                         Path(auth.caminho_usuarios()).parent)

    def test_gravacao_impossivel_nao_derruba(self):
        """Pasta somente-leitura, rede fora: a escolha vale para a sessão.

        Preferência que não persiste é aborrecimento; exceção subindo daqui
        fecharia a aba no meio de um clique de troca de médico.
        """
        arquivo = Path(self._d) / "nao_e_pasta"
        arquivo.write_text("x", encoding="utf-8")
        os.environ["ISOCENTRO_USERS_DIR"] = str(arquivo)
        preferencias.gravar("geovani.pena", CHAVE, ["Dr. A"])
        self.assertIsNone(preferencias.ler("geovani.pena", CHAVE))

    def test_arquivo_ilegivel_nao_derruba(self):
        preferencias.caminho().write_text("{ isto não é json", encoding="utf-8")
        self.assertEqual(preferencias.ler("geovani.pena", CHAVE, []), [])
        preferencias.gravar("geovani.pena", CHAVE, ["Dr. A"])
        self.assertEqual(preferencias.ler("geovani.pena", CHAVE), ["Dr. A"])


class TestGrupoMedicoLembrado(_PastaLimpa):
    """A ponte entre a escolha antiga (por estação) e a nova (por pessoa)."""

    def setUp(self):
        super().setUp()
        from PySide6.QtCore import QSettings
        from isocentro.interface import controle_virtual
        self._cv = controle_virtual
        self._ini = str(Path(self._d) / "estacao.ini")
        # Guardar e DEVOLVER a função — nunca ``del``: o ``del`` apagaria a
        # original do módulo, e os testes seguintes ficariam sem ela.
        self._qs_original = controle_virtual._qsettings_antigo
        controle_virtual._qsettings_antigo = (
            lambda: QSettings(self._ini, QSettings.IniFormat))

    def tearDown(self):
        self._cv._qsettings_antigo = self._qs_original
        super().tearDown()

    def _controle(self, usuario):
        # ``ficha_virtual=None``: o construtor não toca a tela, e o que se
        # testa aqui é de onde vem a lista — não como ela é desenhada.
        return self._cv.ControleFichaVirtual(None, usuario)

    def _gravar_no_antigo(self, nomes):
        cfg = self._cv._qsettings_antigo()
        cfg.setValue(self._cv._CHAVE_QSETTINGS, list(nomes))
        cfg.sync()

    def test_adota_a_escolha_que_estava_na_estacao(self):
        """Sem isto, a mudança apareceria como "o programa esqueceu meu grupo"."""
        self._gravar_no_antigo(["Dr. Principal", "Dr. Colega"])
        u = {"usuario": "geovani.pena", "papel": "medico"}
        self.assertEqual(self._controle(u)._medicos_lembrados(),
                         ["Dr. Principal", "Dr. Colega"])
        # E a adoção é DEFINITIVA: a partir daqui a escolha é da pessoa e vai
        # com ela para qualquer estação.
        self.assertEqual(preferencias.ler(u, self._cv.CHAVE_MEDICOS),
                         ["Dr. Principal", "Dr. Colega"])

    def test_a_preferencia_da_pessoa_manda_no_que_ficou_na_maquina(self):
        """A escolha do colega que usou esta estação não pode voltar por cima."""
        self._gravar_no_antigo(["Dr. Do Colega"])
        u = {"usuario": "geovani.pena", "papel": "medico"}
        preferencias.gravar(u, self._cv.CHAVE_MEDICOS, ["Dr. Meu"])
        self.assertEqual(self._controle(u)._medicos_lembrados(), ["Dr. Meu"])

    def test_sem_nada_gravado_comeca_vazio(self):
        u = {"usuario": "novato", "papel": "medico"}
        self.assertEqual(self._controle(u)._medicos_lembrados(), [])


if __name__ == "__main__":
    unittest.main()
