"""A pasta que o admin aponta tem de valer para TODAS as estações.

Antes, a escolha ia para o ``QSettings`` — no Windows, ``HKEY_CURRENT_USER``:
valia para um usuário do Windows, numa máquina. O admin apontava a pasta certa,
a estação ao lado continuava sem achar relatório nenhum, e a capa nascia vazia
lá sem ninguém entender por quê.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.banco import capa_dados  # noqa: E402
from isocentro.dados import config_servico  # noqa: E402
from isocentro.interface import simulacao  # noqa: E402


class _ConfigLimpa(unittest.TestCase):
    """Aponta a configuração para uma pasta descartável — nunca a do serviço."""

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="config_servico_")
        self._env = {v: os.environ.get(v) for v in
                     ("ISOCENTRO_CONFIG", capa_dados.PASTA_ENV,
                      simulacao.PASTA_ENV)}
        os.environ["ISOCENTRO_CONFIG"] = self._dir
        os.environ.pop(capa_dados.PASTA_ENV, None)
        os.environ.pop(simulacao.PASTA_ENV, None)
        capa_dados.definir_pasta_dados("")
        simulacao.definir_raiz("")

    def tearDown(self):
        for var, valor in self._env.items():
            if valor is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = valor
        capa_dados.definir_pasta_dados("")
        simulacao.definir_raiz("")
        # A pasta do setUp era abandonada: uma por método, e a suíte inteira
        # deixava 1240 `config_servico_*` no %TEMP% desta estação. `ignore_errors`
        # porque o que interessa aqui é não acumular lixo — um resto que o
        # Windows ainda segure não é motivo para derrubar o teste.
        shutil.rmtree(self._dir, ignore_errors=True)


class TestArmazenamento(_ConfigLimpa):

    def test_grava_e_le(self):
        self.assertTrue(config_servico.definir(
            config_servico.PASTA_RELATORIOS, r"C:\relatorios", "geovani"))
        self.assertEqual(
            config_servico.valor(config_servico.PASTA_RELATORIOS),
            r"C:\relatorios")

    def test_guarda_quem_apontou(self):
        """Apontar de onde sai um documento de paciente não pode ser anônimo."""
        config_servico.definir(config_servico.PASTA_RELATORIOS, r"C:\x", "geovani")
        quem, quando = config_servico.autoria(config_servico.PASTA_RELATORIOS)
        self.assertEqual(quem, "geovani")
        self.assertTrue(quando)

    def test_vazio_devolve_ao_padrao(self):
        """É assim que se desfaz um apontamento errado sem ter de adivinhar o
        valor anterior."""
        config_servico.definir(config_servico.PASTA_RELATORIOS, r"C:\x", "g")
        config_servico.definir(config_servico.PASTA_RELATORIOS, "", "g")
        self.assertEqual(
            config_servico.valor(config_servico.PASTA_RELATORIOS), "")

    def test_chave_desconhecida_nao_entra(self):
        """O arquivo é lido por todas as estações; não é depósito de estado de
        tela."""
        self.assertFalse(config_servico.definir("qualquer_coisa", "x", "g"))
        self.assertEqual(config_servico.ler(), {})

    def test_arquivo_corrompido_nao_derruba_o_programa(self):
        """Sem configuração legível, o programa cai nos padrões — que é como
        ele funcionava antes de existir admin."""
        with open(config_servico.caminho(), "w", encoding="utf-8") as fh:
            fh.write("isto nao e json")
        self.assertEqual(config_servico.ler(), {})
        self.assertEqual(
            config_servico.valor(config_servico.PASTA_RELATORIOS), "")

    def test_duas_estacoes_gravando_nao_se_apagam(self):
        erros: list = []

        def trabalhar(i):
            for k in range(20):
                try:
                    config_servico.definir(config_servico.PASTA_RELATORIOS,
                                           f"C:\\p{i}-{k}", f"u{i}")
                except Exception as e:  # noqa: BLE001
                    erros.append(repr(e))

        fios = [threading.Thread(target=trabalhar, args=(i,)) for i in range(6)]
        for t in fios:
            t.start()
        for t in fios:
            t.join()
        self.assertEqual(erros, [])
        with open(config_servico.caminho(), encoding="utf-8") as fh:
            self.assertIn(config_servico.PASTA_RELATORIOS, json.load(fh))


class TestOndeCadaUmManda(_ConfigLimpa):
    """A ordem de precedência — e ela precisa ser visível na tela."""

    def test_o_admin_alcanca_quem_nao_escolheu_nada(self):
        """É o pedido inteiro: apontada a pasta, ela vale para os outros."""
        config_servico.definir(config_servico.PASTA_RELATORIOS, self._dir, "g")
        self.assertEqual(capa_dados.pasta_dados(), self._dir)
        self.assertEqual(capa_dados.origem_da_pasta(), "configuração do serviço")

    def test_a_variavel_da_estacao_manda_na_do_servico(self):
        """Variável de ambiente é decisão de quem MONTOU a estação; não deve
        ser desfeita à distância."""
        config_servico.definir(config_servico.PASTA_RELATORIOS, self._dir, "g")
        os.environ[capa_dados.PASTA_ENV] = r"C:\da_estacao"
        self.assertEqual(capa_dados.pasta_dados(), r"C:\da_estacao")
        self.assertIn(capa_dados.PASTA_ENV, capa_dados.origem_da_pasta())

    def test_a_escolha_da_sessao_manda_em_tudo(self):
        config_servico.definir(config_servico.PASTA_RELATORIOS, self._dir, "g")
        capa_dados.definir_pasta_dados(r"C:\agora")
        self.assertEqual(capa_dados.pasta_dados(), r"C:\agora")
        self.assertEqual(capa_dados.origem_da_pasta(), "escolhida nesta sessão")

    def test_a_raiz_das_simulacoes_segue_a_mesma_regra(self):
        config_servico.definir(config_servico.RAIZ_SIMULACOES,
                               r"\\servidor\Simulacoes", "g")
        self.assertEqual(simulacao.raiz(), r"\\servidor\Simulacoes")


if __name__ == "__main__":
    unittest.main()
