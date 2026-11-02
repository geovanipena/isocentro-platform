"""Uma sessão por usuário: entrar numa estação encerra a da outra.

A conta aberta em duas salas ao mesmo tempo estraga o rastro antes de qualquer
outra coisa: o histórico grava quem marcou o checklist e quem gerou a ficha, e
com o mesmo nome em duas máquinas ele deixa de responder "quem foi".

Cada teste fala de um jeito de errar que a implementação teria: derrubar por
falha de rede, apagar a sessão de quem acabou de entrar, ou trancar o admin
fora das Configurações que ele está justamente ajustando.

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

from isocentro.dados import sessao  # noqa: E402

FISICO = {"usuario": "geovani.pena", "nome": "Geovani", "papel": "fisico"}
ADMIN = {"usuario": "admin", "nome": "Administrador", "papel": "admin"}


class _SessaoLimpa(unittest.TestCase):
    """Pasta descartável, e o estado do módulo devolvido como estava.

    ``_ATUAL`` é global do módulo: um teste que o deixa preenchido faz o
    seguinte conferir a sessão de outro — e o ``discover`` alfabético esconde
    isso até alguém rodar em ordem aleatória.
    """

    def setUp(self):
        self._d = tempfile.mkdtemp(prefix="sessao_")
        self._antes = os.environ.get("ISOCENTRO_USERS_DIR")
        os.environ["ISOCENTRO_USERS_DIR"] = self._d
        self._atual = sessao._ATUAL

    def tearDown(self):
        sessao._ATUAL = self._atual
        if self._antes is None:
            os.environ.pop("ISOCENTRO_USERS_DIR", None)
        else:
            os.environ["ISOCENTRO_USERS_DIR"] = self._antes
        shutil.rmtree(self._d, ignore_errors=True)

    def _outra_estacao(self, usuario) -> dict:
        """Abre a sessão como se fosse OUTRA máquina e devolve a minha de volta.

        Uma segunda estação não existe dentro da suíte: o que a define é o
        token no arquivo, e é ele que o ``abrir`` troca.
        """
        minha = dict(sessao._ATUAL) if sessao._ATUAL else None
        sessao.abrir(usuario)
        sessao._ATUAL = minha
        return minha or {}


class TestSessaoUnica(_SessaoLimpa):

    def test_abrir_registra_e_a_sessao_e_minha(self):
        self.assertTrue(sessao.abrir(FISICO))
        self.assertTrue(sessao.minha_vez())
        self.assertTrue(sessao.caminho().exists())

    def test_login_em_outra_estacao_derruba_esta(self):
        sessao.abrir(FISICO)
        self._outra_estacao(FISICO)
        self.assertFalse(sessao.minha_vez())

    def test_outro_usuario_nao_derruba(self):
        """Duas pessoas em duas estações é o dia normal do serviço."""
        sessao.abrir(FISICO)
        self._outra_estacao({"usuario": "outro.fisico", "papel": "fisico"})
        self.assertTrue(sessao.minha_vez())

    def test_admin_fica_de_fora(self):
        """Quem ajusta as Configurações confere o efeito na estação ao lado."""
        self.assertEqual(sessao.abrir(ADMIN), "")
        self.assertFalse(sessao.vigilancia_ativa())
        self.assertTrue(sessao.minha_vez())

    def test_papel_vem_do_login_e_nao_do_nome_solto(self):
        """Isenção pelo nome permitiria contornar a regra chamando com string."""
        self.assertFalse(sessao.isento("admin"))
        self.assertTrue(sessao.isento(ADMIN))

    def test_dono_diz_onde_a_conta_entrou(self):
        """Sem a máquina, o aviso não distingue "fui eu" de "é outra pessoa"."""
        sessao.abrir(FISICO)
        self._outra_estacao(FISICO)
        dono = sessao.dono(FISICO)
        self.assertIsNotNone(dono)
        self.assertIn("maquina", dono)
        self.assertIn("desde", dono)

    def test_retomar_devolve_a_sessao(self):
        """É o que o novo login na tela travada faz."""
        sessao.abrir(FISICO)
        self._outra_estacao(FISICO)
        self.assertFalse(sessao.minha_vez())
        sessao.abrir(FISICO)
        self.assertTrue(sessao.minha_vez())

    def test_fechar_solta_a_sessao(self):
        sessao.abrir(FISICO)
        sessao.fechar()
        self.assertFalse(sessao.vigilancia_ativa())
        self.assertIsNone(sessao.dono(FISICO))

    def test_fechar_a_estacao_derrubada_nao_derruba_quem_entrou(self):
        """O caso que uma limpeza ingênua quebraria.

        A estação derrubada também é fechada, mais tarde, por quem passa por
        ela. Se o ``fechar`` apagasse a entrada sem conferir o token, ele
        apagaria a sessão de quem acabou de entrar na outra máquina — e essa
        pessoa seria travada por um fechamento que não foi dela.
        """
        sessao.abrir(FISICO)
        self._outra_estacao(FISICO)
        de_la = sessao.dono(FISICO)
        sessao.fechar()                      # a estação derrubada, fechando
        self.assertEqual(sessao.dono(FISICO), de_la)

    def test_arquivo_ilegivel_nao_derruba_ninguem(self):
        """Rede piscando não pode trancar o serviço inteiro fora do programa.

        "Não sei" e "a sessão acabou" são coisas diferentes: só a segunda
        derruba, e quem está na sala de comando não teria o que fazer com um
        aviso que a primeira produzisse.
        """
        sessao.abrir(FISICO)
        sessao.caminho().write_text("{ isto não é json", encoding="utf-8")
        self.assertTrue(sessao.minha_vez())

    def test_arquivo_apagado_nao_derruba_ninguem(self):
        sessao.abrir(FISICO)
        sessao.caminho().unlink()
        self.assertTrue(sessao.minha_vez())

    def test_sem_conseguir_gravar_nao_ha_vigilancia(self):
        """Falha de escrita não pode virar vigilância.

        Sem registro no arquivo, a conferência seguinte não acharia o token
        deste processo — e a estação se trancaria sozinha a cada meio minuto,
        por um login que nunca existiu.
        """
        arquivo = Path(self._d) / "nao_e_pasta"
        arquivo.write_text("x", encoding="utf-8")
        os.environ["ISOCENTRO_USERS_DIR"] = str(arquivo)
        self.assertEqual(sessao.abrir(FISICO), "")
        self.assertFalse(sessao.vigilancia_ativa())
        self.assertTrue(sessao.minha_vez())


if __name__ == "__main__":
    unittest.main()
