"""Correções de cadastro: o conserto feito à mão tem de durar.

Os relatórios que alimentam a capa são lidos, nunca escritos, e são retratos do
dia da exportação. Quando o cadastro traz o sexo errado, quem corrige é a pessoa
que monta a ficha — e antes disso a correção morria no fechamento da tela: o
paciente voltava errado no dia seguinte e alguém corrigia de novo, toda vez.

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dados import correcoes  # noqa: E402


class _PastaLimpa(unittest.TestCase):
    """Aponta as correções para uma pasta descartável — nunca a do serviço."""

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="correcoes_")
        os.environ["ISOCENTRO_CORRECOES"] = self._dir

    def tearDown(self):
        os.environ.pop("ISOCENTRO_CORRECOES", None)


class TestArmazenamento(_PastaLimpa):

    def test_grava_e_le(self):
        correcoes.salvar("9000016BET", {"sexo": "Feminino"}, "geovani")
        self.assertEqual(correcoes.ler("9000016BET"), {"sexo": "Feminino"})

    def test_o_id_e_comparado_normalizado(self):
        """O mesmo registro aparece com espaço ou traço conforme quem digitou."""
        correcoes.salvar("9000016BET", {"sexo": "Feminino"})
        self.assertEqual(correcoes.ler(" 9000016-bet "), {"sexo": "Feminino"})

    def test_valor_vazio_apaga_a_correcao(self):
        """É assim que se desfaz um conserto errado: devolver ao original."""
        correcoes.salvar("1", {"sexo": "Feminino", "convenio": "Unimed"})
        correcoes.salvar("1", {"sexo": ""})
        self.assertEqual(correcoes.ler("1"), {"convenio": "Unimed"})

    def test_paciente_sem_correcao_nao_deixa_rastro(self):
        """O arquivo é lido a cada capa: entrada vazia é peso sem conteúdo."""
        correcoes.salvar("1", {"sexo": "Feminino"})
        correcoes.salvar("1", {"sexo": ""})
        dados = json.loads(correcoes.caminho().read_text(encoding="utf-8"))
        self.assertEqual(dados["pacientes"], {})

    def test_so_os_campos_previstos(self):
        """O REGISTRO não entra: ele é a chave, e "corrigir" a chave seria
        criar outra pessoa."""
        correcoes.salvar("1", {"registro": "OUTRO", "sexo": "Feminino"})
        self.assertEqual(correcoes.ler("1"), {"sexo": "Feminino"})

    def test_um_campo_novo_nao_apaga_o_anterior(self):
        correcoes.salvar("1", {"sexo": "Feminino"})
        correcoes.salvar("1", {"convenio": "Unimed"})
        self.assertEqual(correcoes.ler("1"),
                         {"sexo": "Feminino", "convenio": "Unimed"})

    def test_guarda_quem_e_quando(self):
        """Dado de paciente que sobrescreve o sistema oficial não é anônimo."""
        correcoes.salvar("1", {"sexo": "Feminino"}, "geovani")
        quem, quando = correcoes.autoria("1")
        self.assertEqual(quem, "geovani")
        self.assertTrue(quando)

    def test_sem_registro_nao_grava(self):
        self.assertEqual(correcoes.salvar("", {"sexo": "Feminino"}), {})
        self.assertEqual(correcoes.ler(""), {})

    def test_arquivo_corrompido_nao_derruba_a_capa(self):
        correcoes.caminho().write_text("{isto não é json", encoding="utf-8")
        self.assertEqual(correcoes.ler("1"), {})

    def test_arquivo_ausente(self):
        self.assertEqual(correcoes.ler("1"), {})
        self.assertEqual(correcoes.autoria("1"), ("", ""))


class TestAplicar(_PastaLimpa):
    """A correção entra por cima do que o relatório trouxe."""

    class _Capa:
        def __init__(self, **kw):
            self.registro = kw.pop("registro", "")
            for c in correcoes.CAMPOS:
                setattr(self, c, kw.get(c, ""))

    def test_sobrescreve_o_relatorio(self):
        correcoes.salvar("1", {"sexo": "Feminino"})
        capa = self._Capa(registro="1", sexo="Masculino", convenio="Ipasgo")
        aplicados = correcoes.aplicar(capa)
        self.assertEqual(capa.sexo, "Feminino")
        self.assertEqual(aplicados, ["sexo"])
        # O que não foi corrigido continua vindo do relatório e acompanhando
        # as atualizações dele.
        self.assertEqual(capa.convenio, "Ipasgo")

    def test_sem_correcao_nao_toca_em_nada(self):
        capa = self._Capa(registro="1", sexo="Masculino")
        self.assertEqual(correcoes.aplicar(capa), [])
        self.assertEqual(capa.sexo, "Masculino")

    def test_correcao_igual_ao_relatorio_nao_conta_como_aplicada(self):
        correcoes.salvar("1", {"sexo": "Feminino"})
        capa = self._Capa(registro="1", sexo="Feminino")
        self.assertEqual(correcoes.aplicar(capa), [])


class TestDuasEstacoesAoMesmoTempo(_PastaLimpa):
    """Corrigir dois pacientes ao mesmo tempo não pode perder correção.

    O arquivo é gravado INTEIRO a cada correção. Sem exclusão mútua no ciclo
    ler→alterar→gravar, quem lê antes e grava depois apaga o trabalho do outro —
    e a correção some sem ninguém perceber, que é o desfecho pior: o paciente
    reabre errado e a pessoa acha que esqueceu de salvar.
    """

    def test_nenhuma_correcao_se_perde(self):
        erros: list = []

        def trabalhar(inicio):
            for k in range(inicio, 240, 8):
                try:
                    correcoes.salvar(f"P{k}", {"sexo": "Feminino"}, "geovani")
                except Exception as e:  # noqa: BLE001
                    erros.append(repr(e))

        fios = [threading.Thread(target=trabalhar, args=(i,)) for i in range(8)]
        for t in fios:
            t.start()
        for t in fios:
            t.join()

        self.assertEqual(erros, [])
        with open(correcoes.caminho(), encoding="utf-8") as fh:
            gravados = json.load(fh)["pacientes"]
        self.assertEqual(set(gravados), {f"P{k}" for k in range(240)})


if __name__ == "__main__":
    unittest.main()
