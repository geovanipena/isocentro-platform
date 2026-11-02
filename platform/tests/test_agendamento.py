"""Expandir/colapsar dias do agendamento (modo dia-a-dia).

Rodar:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dominio import agendamento as ag  # noqa: E402


class TestExpandirDias(unittest.TestCase):
    def test_bloco_vira_uma_linha_por_dia(self):
        etapas = [{"planos": [0, 1], "fracoes": 3}]
        dias = ag.expandir_dias(etapas)
        self.assertEqual(dias, [
            {"planos": [0, 1], "fracoes": 1},
            {"planos": [0, 1], "fracoes": 1},
            {"planos": [0, 1], "fracoes": 1},
        ])

    def test_sequencial_expande_na_ordem(self):
        etapas = [{"planos": [0], "fracoes": 2},
                  {"planos": [1], "fracoes": 1}]
        self.assertEqual([d["planos"] for d in ag.expandir_dias(etapas)],
                         [[0], [0], [1]])


class TestColapsarDias(unittest.TestCase):
    def test_dias_iguais_viram_bloco(self):
        etapas = [{"planos": [0, 1], "fracoes": 1}] * 3
        blocos = ag.colapsar_dias(etapas)
        self.assertEqual(blocos, [{"planos": [0, 1], "fracoes": 3}])

    def test_muda_de_conjunto_abre_bloco_novo(self):
        etapas = [{"planos": [0, 1], "fracoes": 2},
                  {"planos": [1], "fracoes": 2}]
        blocos = ag.colapsar_dias(etapas)
        self.assertEqual(blocos, [
            {"planos": [0, 1], "fracoes": 2},
            {"planos": [1], "fracoes": 2},
        ])

    def test_expandir_e_colapsar_sao_inversos_no_bloco_simples(self):
        etapas = [{"planos": [0, 1], "fracoes": 5}]
        self.assertEqual(ag.colapsar_dias(ag.expandir_dias(etapas)), etapas)

    def test_fracoes_por_plano_preservado_no_ciclo(self):
        etapas = [{"planos": [0, 1], "fracoes": 3},
                  {"planos": [2], "fracoes": 2}]
        antes = ag.fracoes_por_plano(etapas, 3)
        depois = ag.fracoes_por_plano(ag.expandir_dias(etapas), 3)
        self.assertEqual(antes, depois)


class TestMontarPorDiaInicio(unittest.TestCase):
    def test_espaco_por_fracionamento(self):
        self.assertEqual(ag.espaco_fracionamento("Dias alter."), 2)
        self.assertEqual(ag.espaco_fracionamento("1x dia"), 1)
        self.assertEqual(ag.espaco_fracionamento("Única"), 1)
        self.assertEqual(ag.espaco_fracionamento("2x sem."), 3)

    def test_todos_dia1_alternado_viram_um_bloco(self):
        planos = [{"fracoes": 3, "dia_inicio": 1, "fracionamento": "Dias alter."}
                  for _ in range(4)]
        col = ag.colapsar_dias(ag.montar_por_dia_inicio(planos))
        self.assertEqual(col, [{"planos": [0, 1, 2, 3], "fracoes": 3}])
        self.assertEqual(ag.fracoes_por_plano(col, 4), [3, 3, 3, 3])

    def test_escalonado_interliga_e_preserva_fracoes(self):
        planos = [{"fracoes": 3, "dia_inicio": d, "fracionamento": "Dias alter."}
                  for d in (1, 2)]
        dias = ag.montar_por_dia_inicio(planos)
        # A em 1,3,5 e B em 2,4,6 → A,B,A,B,A,B
        self.assertEqual([e["planos"] for e in dias],
                         [[0], [1], [0], [1], [0], [1]])
        self.assertEqual(ag.fracoes_por_plano(dias, 2), [3, 3])

    def test_dia_inicio_desloca_o_comeco(self):
        dias = ag.montar_por_dia_inicio(
            [{"fracoes": 2, "dia_inicio": 3, "fracionamento": "1x dia"}])
        self.assertEqual(dias, [{"planos": [0], "fracoes": 1},
                                {"planos": [0], "fracoes": 1}])


class TestOrdemSequencial(unittest.TestCase):
    def test_ordena_por_numero_do_rotulo(self):
        # Plano nº 1 (base) antes do nº 2 (boost), mesmo carregados fora de ordem.
        self.assertEqual(ag.ordem_por_numero(["2 iSNC_60Gy", "1 iSNC_40Gy"]), [1, 0])
        self.assertEqual(ag.ordem_por_numero(["3 C", "1 A", "2 B"]), [1, 2, 0])

    def test_sem_numero_mantem_ordem(self):
        self.assertEqual(ag.ordem_por_numero(["Boost", "Mama"]), [0, 1])

    def test_modelo_sequencial_respeita_ordem(self):
        # fracoes na ordem de carregamento: idx0=60Gy(10fx), idx1=40Gy(20fx).
        et = ag.modelo_sequencial([10, 20], ordem=[1, 0])
        self.assertEqual(et, [{"planos": [1], "fracoes": 20},
                              {"planos": [0], "fracoes": 10}])

    def test_modelo_sequencial_sem_ordem_natural(self):
        self.assertEqual(ag.modelo_sequencial([5, 8]),
                         [{"planos": [0], "fracoes": 5},
                          {"planos": [1], "fracoes": 8}])

    def test_modelo_alternado_reveza_dia_a_dia(self):
        # Dois planos de 3 fx → 1, 2, 1, 2, 1, 2 (um dia de cada por vez).
        et = ag.modelo_alternado([3, 3])
        self.assertEqual(et, [{"planos": [0], "fracoes": 1},
                              {"planos": [1], "fracoes": 1}] * 3)

    def test_modelo_alternado_plano_curto_sai_do_rodizio(self):
        # idx0 esgota (2 fx) e idx1 segue sozinho (4 fx).
        et = ag.modelo_alternado([2, 4])
        planos = [e["planos"][0] for e in et]
        self.assertEqual(planos, [0, 1, 0, 1, 1, 1])

    def test_modelo_alternado_respeita_ordem(self):
        et = ag.modelo_alternado([2, 2], ordem=[1, 0])
        self.assertEqual([e["planos"][0] for e in et], [1, 0, 1, 0])

    def test_aplicar_modelo_em_mantem_nao_selecionados(self):
        # 3 planos juntos por 2 dias; aplico alternado só em {0,2}. O plano 1
        # fica intacto nos dias 1 e 2; 0 e 2 revezam ao longo da linha do tempo.
        atual = [{"planos": [0, 1, 2], "fracoes": 2}]
        modelo = ag.modelo_alternado([2, 2, 2], ordem=[0, 2])
        out = ag.aplicar_modelo_em(atual, modelo, {0, 2})
        self.assertEqual(out, [{"planos": [0, 1], "fracoes": 1},
                               {"planos": [1, 2], "fracoes": 1},
                               {"planos": [0], "fracoes": 1},
                               {"planos": [2], "fracoes": 1}])

    def test_aplicar_modelo_em_selecao_total_equivale_ao_modelo(self):
        atual = [{"planos": [0, 1], "fracoes": 3}]
        modelo = ag.modelo_sequencial([2, 2], ordem=[0, 1])
        out = ag.aplicar_modelo_em(atual, modelo, {0, 1})
        self.assertEqual(out, modelo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
