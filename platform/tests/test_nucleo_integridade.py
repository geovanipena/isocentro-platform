"""O verificador do log e o ``nucleo.gravar``, sem banco (R-18).

O que estes testes guardam: linha do log alterada ou apagada que o verificador
não aponta (a inspeção aceitaria um histórico mexido), e gravação que chega
ao banco sem autor, em tabela alheia ou com nome de coluna carregando SQL. Os
mesmos caminhos contra o PostgreSQL de verdade estão no ``test_postgres.py``.
"""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from isocentro.nucleo.gravacao import (
    GravacaoRecusada, Gravado, LinhaNova, gravar)
from isocentro.nucleo.integridade import (
    GENESE, Ancora, LinhaDeLog, hash_da_linha, verificar)

INICIO = datetime(2026, 10, 27, 11, 0, tzinfo=timezone.utc)


def _corrente(n: int) -> list[LinhaDeLog]:
    linhas, anterior = [], GENESE
    for i in range(1, n + 1):
        linha = LinhaDeLog(
            posicao=i, quando=INICIO + timedelta(seconds=i, microseconds=7),
            quem="físico.ção", modulo="teste", tabela="teste.coisa",
            registro=str(i), substitui=None if i < 4 else str(i - 1),
            versao_origem=None, hash_anterior=anterior, hash=b"")
        linha = replace(linha, hash=hash_da_linha(linha, anterior))
        linhas.append(linha)
        anterior = linha.hash
    return linhas


def _refazer_de(linhas: list[LinhaDeLog], indice: int) -> list[LinhaDeLog]:
    """Reescreve a corrente inteira a partir de ``indice``, como faria quem tem DDL."""
    novas = list(linhas[:indice])
    anterior = novas[-1].hash if novas else GENESE
    for linha in linhas[indice:]:
        linha = replace(linha, hash_anterior=anterior)
        linha = replace(linha, hash=hash_da_linha(linha, anterior))
        novas.append(linha)
        anterior = linha.hash
    return novas


class TestVerificador(unittest.TestCase):

    def test_corrente_integra_nao_aponta_nada(self):
        self.assertEqual(verificar(_corrente(6)), [])

    def test_linha_alterada_e_apontada_sozinha(self):
        """Só a linha mexida aparece: as seguintes guardam o próprio
        ``hash_anterior``, e a lista não deve mandar o físico investigar o
        log inteiro por causa de uma linha."""
        linhas = _corrente(6)
        linhas[2] = replace(linhas[2], quem="outra pessoa")
        achados = verificar(linhas)
        self.assertEqual([(d.posicao, d.registro) for d in achados], [(3, "3")])
        self.assertIn("alterada", achados[0].motivo)

    def test_linha_apagada_no_meio_aponta_a_posicao(self):
        linhas = _corrente(6)
        del linhas[1]
        achados = verificar(linhas)
        self.assertEqual(achados[0].posicao, 2)
        self.assertIsNone(achados[0].registro)
        self.assertIn("apagada", achados[0].motivo)

    def test_corrente_reescrita_so_a_ancora_pega(self):
        """Quem tem DDL refaz todos os hashes de um ponto em diante: sem
        âncora, a corrente fecha. É o caso que justifica a âncora fora do
        banco (AD-32)."""
        original = _corrente(6)
        mexida = list(original)
        mexida[1] = replace(mexida[1], quem="outra pessoa")
        mexida = _refazer_de(mexida, 1)
        self.assertEqual(verificar(mexida), [])
        achados = verificar(mexida, [Ancora(4, original[3].hash)])
        self.assertEqual([d.posicao for d in achados], [4])
        self.assertIn("âncora", achados[0].motivo)

    def test_ultimas_linhas_apagadas_so_a_ancora_pega(self):
        original = _corrente(6)
        self.assertEqual(verificar(original[:4]), [])
        achados = verificar(original[:4], [Ancora(6, original[5].hash)])
        self.assertEqual([d.posicao for d in achados], [6])

    def test_ancora_que_bate_nao_aponta_nada(self):
        original = _corrente(6)
        self.assertEqual(verificar(original, [Ancora(6, original[5].hash)]), [])

    def test_hora_sem_fuso_e_recusada(self):
        """Sem fuso não há instante: adivinhar daria hash diferente conforme a
        estação, e o verificador acusaria linha íntegra."""
        linha = replace(_corrente(1)[0], quando=datetime(2026, 10, 27, 11, 0))
        with self.assertRaises(ValueError):
            hash_da_linha(linha, GENESE)

    def test_o_mesmo_instante_em_outro_fuso_da_o_mesmo_hash(self):
        linha = _corrente(1)[0]
        brasilia = timezone(timedelta(hours=-3))
        outra = replace(linha, quando=linha.quando.astimezone(brasilia))
        self.assertEqual(hash_da_linha(linha, GENESE),
                         hash_da_linha(outra, GENESE))

    def test_fronteira_entre_campos_nao_se_imita(self):
        """Só com um separador (sem o comprimento na frente), ``quem='a:b',
        modulo='c'`` e ``quem='a', modulo='b:c'`` dariam o mesmo texto e o
        mesmo hash: trocar a autoria passaria pelo verificador."""
        linha = _corrente(1)[0]
        a = replace(linha, quem="a:b", modulo="c")
        b = replace(linha, quem="a", modulo="b:c")
        self.assertNotEqual(hash_da_linha(a, GENESE), hash_da_linha(b, GENESE))


class PortaFalsa:
    def __init__(self, donos=None):
        self.donos = donos if donos is not None else {"teste.coisa": "teste"}
        self.chamadas = []

    def dono_de(self, tabela):
        return self.donos.get(tabela)

    def inserir_com_log(self, tabela, dados, linha):
        self.chamadas.append((tabela, dados, linha))
        return Gravado(tabela, "1", 1)


class TestGravar(unittest.TestCase):

    def _gravar(self, porta=None, **kw):
        campos = dict(modulo="teste", tabela="teste.coisa",
                      dados={"valor": "a"}, quem="geovani")
        campos.update(kw)
        return gravar(porta or PortaFalsa(), **campos)

    def test_grava_e_passa_a_linha_de_log(self):
        porta = PortaFalsa()
        self._gravar(porta, versao_origem="RTPLAN 1.2", substitui="7")
        tabela, dados, linha = porta.chamadas[0]
        self.assertEqual(linha, LinhaNova("geovani", "teste", "teste.coisa",
                                          "7", "RTPLAN 1.2"))
        with self.assertRaises(TypeError):
            dados["valor"] = "mudado pela porta"

    def test_recusas_antes_de_chegar_ao_banco(self):
        """Cada uma destas, passando, viraria linha de log sem autor, gravação
        em tabela alheia ou SQL dentro do nome de uma coluna."""
        casos = {
            "tabela de outro módulo": dict(modulo="plano"),
            "tabela fora do registro": dict(tabela="teste.outra"),
            "tabela sem schema": dict(tabela="coisa"),
            "sem autor": dict(quem="  "),
            "autor que não é texto": dict(quem=None),
            "registro vazio": dict(dados={}),
            "coluna com SQL": dict(dados={"valor) VALUES (1); --": "x"}),
            "coluna com maiúscula": dict(dados={"Valor": "x"}),
            "id escolhido por quem grava": dict(dados={"id": 5}),
            "correção por coluna": dict(dados={"substitui": "3"}),
            "correção vazia": dict(substitui=""),
            "versão de origem vazia": dict(versao_origem=" "),
            "módulo com acento": dict(modulo="médico"),
        }
        for nome, kw in casos.items():
            with self.subTest(nome):
                porta = PortaFalsa()
                with self.assertRaises(GravacaoRecusada):
                    self._gravar(porta, **kw)
                self.assertEqual(porta.chamadas, [])


if __name__ == "__main__":
    unittest.main()
