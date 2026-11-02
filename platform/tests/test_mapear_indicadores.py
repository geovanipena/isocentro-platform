"""O ``tools/mapear_indicadores.py`` roda na clínica e a saída circula.

A promessa dele é não ler nenhuma linha de paciente — só catálogo e contagem —,
e é isso que deixa o relatório ser lido, guardado e mandado. Uma pergunta nova
que puxasse ``PatientFullName`` para "conferir um caso" quebraria a promessa
calada: o arquivo continuaria com a mesma cara, agora com nomes dentro.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import mapear_indicadores as mi  # noqa: E402

# Colunas que identificam paciente no data warehouse do ARIA. ``DimPatientID``
# fica de fora de propósito: é a chave substituta do warehouse, usada para JUNTAR
# tabelas, e não sai na saída; ``PatientId`` (sem o ``Dim``) é o registro.
_COLUNAS_DE_PACIENTE = re.compile(
    r"Patient(Full)?Name|(?<!Dim)PatientId\b|FirstName|LastName|BirthDate"
    r"|DateOfBirth",
    re.IGNORECASE)


class _CursorFalso:
    def __init__(self, registro):
        self._registro = registro

    def execute(self, sql, *params):
        self._registro.append(sql)

    def fetchall(self):
        return []


class _ConexaoFalsa:
    def __init__(self):
        self.consultas: list[str] = []

    def cursor(self):
        return _CursorFalso(self.consultas)


class TestNenhumaLinhaDePaciente(unittest.TestCase):

    def _rodar_todas(self) -> list[str]:
        cx = _ConexaoFalsa()
        for pergunta in (mi.pergunta_encerramento, mi.pergunta_frequencia,
                         mi.pergunta_atividades, mi.pergunta_braquiterapia):
            pergunta(cx)
        return cx.consultas

    def test_nenhuma_consulta_seleciona_coluna_de_paciente(self):
        """Juntar por ``DimPatientID`` pode; trazer nome ou registro, não."""
        consultas = self._rodar_todas()
        self.assertTrue(consultas, "as perguntas não consultaram nada")
        for sql in consultas:
            self.assertIsNone(_COLUNAS_DE_PACIENTE.search(sql),
                              f"consulta lê coluna de paciente:\n{sql}")

    def test_texto_livre_da_prescricao_nao_e_amostrado(self):
        """Tipo com muitos valores distintos é texto livre, onde o nome do
        paciente aparece sem ninguém ter pedido — não se amostra. O tipo 7 (a
        frequência, poucos valores) SE amostra: a primeira versão o excluía por
        engano e escondeu a resposta que o mapeador existia para dar."""
        class _ConexaoComTipos(_ConexaoFalsa):
            def cursor(self_inner):
                outer = self_inner

                class _C(_CursorFalso):
                    def fetchall(self_c):
                        if "COUNT(DISTINCT pp.PropertyValue)" in outer.consultas[-1]:
                            return [(7, 100, 5), (9, 800, 400)]
                        return []
                return _C(outer.consultas)

        cx = _ConexaoComTipos()
        mi.pergunta_frequencia(cx)
        amostras = [c for c in cx.consultas if "WHERE pp.PropertyType = ?" in c]
        # Só o tipo 7 (5 valores) é amostrado; o 9 (400 valores) é texto livre.
        self.assertEqual(len(amostras), 1)


if __name__ == "__main__":
    unittest.main()
