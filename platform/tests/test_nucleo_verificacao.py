"""O contrato da verificação (`isocentro/nucleo/verificacao.py`, R-77).

O que estes testes guardam é o que, quebrado, faz um plano parecer conferido
sem ter sido: avaliador que estoura e some, falta de dado contada como
aprovação, verificação sem fonte entrando no catálogo, tolerância de
literatura passando por derivada do serviço, sombra gerando alerta e caso
semeado entrando no indicador. A gravação real é da R-20; aqui a porta é a
``PortaEmMemoria``, que existe só neste arquivo.
"""
from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from isocentro.nucleo import verificacao as v
from isocentro.nucleo.verificacao import (
    Avaliacao, CadastroRecusado, Entrada, Estado, Execucao, Origem,
    OrigemTolerancia, PortaDeGravacao, Resultado, Tolerancia, Verificacao,
    VerificacaoPodada, alertas, executar, para_indicador)

FONTE = Path(v.__file__)
AGORA = datetime(2026, 10, 23, 8, 0)


class PortaEmMemoria:
    """A implementação de teste da porta: guarda numa lista, em ordem."""

    def __init__(self):
        self.execucoes: list[Execucao] = []

    def gravar_execucao(self, execucao: Execucao) -> None:
        self.execucoes.append(execucao)


def _conforme(_dados):
    return Avaliacao(Resultado.CONFORME, evidencia={"medido": 1.0})


def _verif(avaliador=_conforme, **kw):
    campos = dict(id="plano.fracoes", versao="1.0.0",
                  regra="nº de frações do plano = prescrição",
                  fontes=("fichas/atividades/C05.md",), gatilho="evento",
                  responsavel="fisico", avaliador=avaliador,
                  severidade="alta")
    campos.update(kw)
    return Verificacao(**campos)


def _entrada(dados=None, **kw):
    campos = dict(objeto="plano:1", versao="v1",
                  dados={"fracoes": 25} if dados is None else dados)
    campos.update(kw)
    return Entrada(**campos)


def _rodar(verif, entrada=None, origem=Origem.PRODUCAO, porta=None):
    porta = porta if porta is not None else PortaEmMemoria()
    return executar(verif, entrada or _entrada(), porta, origem=origem,
                    agora=lambda: AGORA)


class TestResultados(unittest.TestCase):

    def test_sao_os_cinco_da_espinha(self):
        self.assertEqual({r.value for r in Resultado},
                         {"conforme", "nao_conforme", "nao_aplicavel",
                          "indeterminado", "erro"})

    def test_a_porta_em_memoria_cumpre_o_protocolo(self):
        porta: PortaDeGravacao = PortaEmMemoria()
        e = _rodar(_verif(), porta=porta)
        self.assertEqual(porta.execucoes, [e])
        self.assertEqual(e.quando, AGORA)
        self.assertEqual(e.evidencia, {"medido": 1.0})
        self.assertTrue(e.conta_como_conforme)


class TestOMotor(unittest.TestCase):

    def test_excecao_do_avaliador_vira_erro_com_a_mensagem(self):
        def estoura(_dados):
            raise ZeroDivisionError("tabela de TMR vazia")
        e = _rodar(_verif(estoura))
        self.assertIs(e.resultado, Resultado.ERRO)
        self.assertIn("tabela de TMR vazia", e.motivo)
        self.assertIn("ZeroDivisionError", e.motivo)
        self.assertFalse(e.conta_como_conforme)

    def test_sem_dado_e_indeterminado_com_motivo_e_o_avaliador_nem_roda(self):
        chamado = []

        def anota(dados):
            chamado.append(dados)
            return Avaliacao(Resultado.CONFORME)
        e = _rodar(_verif(anota), Entrada("plano:1", "v1", None))
        self.assertIs(e.resultado, Resultado.INDETERMINADO)
        self.assertTrue(e.motivo)
        self.assertEqual(chamado, [])

    def test_chave_requerida_ausente_e_indeterminado_dizendo_qual(self):
        e = _rodar(_verif(requer=("fracoes", "dose_total")),
                   _entrada({"fracoes": 25, "dose_total": None}))
        self.assertIs(e.resultado, Resultado.INDETERMINADO)
        self.assertIn("dose_total", e.motivo)
        self.assertNotIn("fracoes", e.motivo)

    def test_o_avaliador_que_diz_indeterminado_com_motivo_passa(self):
        e = _rodar(_verif(lambda d: Avaliacao(Resultado.INDETERMINADO,
                                              "sem tabela da máquina")))
        self.assertIs(e.resultado, Resultado.INDETERMINADO)
        self.assertEqual(e.motivo, "sem tabela da máquina")

    def test_indeterminado_ou_erro_sem_motivo_vira_erro_do_avaliador(self):
        for r in (Resultado.INDETERMINADO, Resultado.ERRO):
            with self.subTest(r=r):
                e = _rodar(_verif(lambda d, r=r: Avaliacao(r, "  ")))
                self.assertIs(e.resultado, Resultado.ERRO)
                self.assertIn("sem motivo", e.motivo)

    def test_devolucao_fora_do_contrato_vira_erro(self):
        for devolve in (True, "conforme", None,
                        Avaliacao("aprovado"),
                        Avaliacao(Resultado.CONFORME, evidencia=[1, 2]),
                        Avaliacao(Resultado.CONFORME, evidencia=["ab", "cd"])):
            with self.subTest(devolve=devolve):
                e = _rodar(_verif(lambda d, x=devolve: x))
                self.assertIs(e.resultado, Resultado.ERRO)
                self.assertTrue(e.motivo)

    def test_sem_versao_do_objeto_e_indeterminado(self):
        # Sem versão, a execução vigente da R-20 não distingue o plano antigo
        # do novo, e o resultado de um valeria para o outro.
        e = _rodar(_verif(), _entrada(versao="  "))
        self.assertIs(e.resultado, Resultado.INDETERMINADO)
        self.assertIn("versão", e.motivo)

    def test_dados_que_nao_sao_mapa_viram_erro_e_nao_estouram(self):
        e = _rodar(_verif(requer=("fracoes",)), _entrada([("fracoes", 25)]))
        self.assertIs(e.resultado, Resultado.ERRO)
        self.assertIn("list", e.motivo)

    def test_avaliador_nao_muda_a_entrada_registrada(self):
        def normaliza(d):
            d["fracoes"] = 0
            return Avaliacao(Resultado.CONFORME)
        entrada = _entrada({"fracoes": 25})
        e = _rodar(_verif(normaliza), entrada)
        self.assertIs(e.resultado, Resultado.ERRO)
        self.assertEqual(e.entrada.dados, {"fracoes": 25})

    def test_motivo_que_nao_e_texto_e_preservado(self):
        e = _rodar(_verif(lambda d: Avaliacao(Resultado.INDETERMINADO,
                                              KeyError("tmr"))))
        self.assertIs(e.resultado, Resultado.INDETERMINADO)
        self.assertIn("tmr", e.motivo)

    def test_hora_padrao_tem_fuso(self):
        e = executar(_verif(), _entrada(), PortaEmMemoria())
        self.assertIsNotNone(e.quando.tzinfo)

    def test_entrada_sem_objeto_e_recusada(self):
        with self.assertRaises(ValueError):
            Entrada(" ", "v1", {})

    def test_resultado_em_texto_e_aceito_como_o_enum(self):
        e = _rodar(_verif(lambda d: Avaliacao("nao_conforme")))
        self.assertIs(e.resultado, Resultado.NAO_CONFORME)

    def test_so_conforme_conta_como_conforme(self):
        for r in Resultado:
            motivo = "x" if r in v.PEDEM_MOTIVO else ""
            with self.subTest(r=r):
                e = _rodar(_verif(lambda d, r=r, m=motivo: Avaliacao(r, m)))
                self.assertEqual(e.conta_como_conforme,
                                 r is Resultado.CONFORME)

    def test_falha_da_porta_sobe(self):
        class Quebrada:
            def gravar_execucao(self, _e):
                raise OSError("banco fora")
        with self.assertRaises(OSError):
            _rodar(_verif(), porta=Quebrada())

    def test_podada_nao_executa(self):
        porta = PortaEmMemoria()
        with self.assertRaises(VerificacaoPodada):
            _rodar(_verif(estado="podada"), porta=porta)
        self.assertEqual(porta.execucoes, [])


class TestCadastro(unittest.TestCase):

    def test_nasce_em_sombra(self):
        self.assertIs(_verif().estado, Estado.SOMBRA)
        self.assertEqual(_verif().modulo, "plano")

    def test_sem_fonte_e_recusado(self):
        for fontes in ((), None, ("",), ("  ",), ("ficha.md", "")):
            with self.subTest(fontes=fontes):
                with self.assertRaises(CadastroRecusado):
                    _verif(fontes=fontes)

    def test_fonte_em_texto_solto_e_uma_fonte_so(self):
        self.assertEqual(_verif(fontes="fichas/atividades/C05.md").fontes,
                         ("fichas/atividades/C05.md",))

    def test_texto_do_cadastro_entra_aparado(self):
        verif = _verif(versao=" 1.0.0 ", requer=(" fracoes",))
        self.assertEqual(verif.versao, "1.0.0")
        self.assertEqual(verif.requer, ("fracoes",))

    def test_chave_requerida_que_nao_e_texto_e_recusada(self):
        for requer in (("fracoes", 1), ("",), (None,)):
            with self.subTest(requer=requer):
                with self.assertRaises(CadastroRecusado):
                    _verif(requer=requer)

    def test_id_fora_de_modulo_ponto_nome_e_recusado(self):
        for id_ in ("fracoes", "Plano.fracoes", "plano.fracoes.x", ".fracoes",
                    "plano.", "plano fracoes", None):
            with self.subTest(id_=id_):
                with self.assertRaises(CadastroRecusado):
                    _verif(id=id_)

    def test_valor_fora_do_vocabulario_e_recusado(self):
        for campo, valor in (("severidade", "bloqueante"),
                             ("estado", "ligada"), ("gatilho", "manual")):
            with self.subTest(campo=campo):
                with self.assertRaises(CadastroRecusado):
                    _verif(**{campo: valor})

    def test_tolerancia_sem_origem_e_recusada(self):
        for origem in (None, "", "achismo"):
            with self.subTest(origem=origem):
                with self.assertRaises(CadastroRecusado):
                    Tolerancia("±3%", origem, referencia="TG-142")

    def test_literatura_exige_referencia(self):
        with self.assertRaises(CadastroRecusado):
            Tolerancia("±3%", "literatura")
        t = Tolerancia("±3%", "literatura", referencia="TG-142 Tab. V")
        self.assertIs(_verif(tolerancia=t).tolerancia, t)

    def test_servico_exige_data_e_metodo(self):
        for kw in ({"metodo": "TG-218, I-MR de 20 planos"},
                   {"data": date(2026, 10, 1)},
                   {"data": datetime(2026, 10, 1), "metodo": "TG-218"},
                   {"data": "2026-10-01", "metodo": "TG-218"}):
            with self.subTest(kw=kw):
                with self.assertRaises(CadastroRecusado):
                    Tolerancia("±3%", "servico", **kw)
        Tolerancia("±3%", "servico", data=date(2026, 10, 1),
                   metodo="TG-218, I-MR de 20 planos")

    def test_provisoria_exige_o_item_de_decisoes_sem_base(self):
        """Provisório sem o número do item não tem como ser achado quando o
        físico decidir, e ficaria provisório para sempre (R-82)."""
        # Item 22: o limite de usos da máscara, que o código já usa sem fonte.
        for decisao in (None, 0, -22, True, "22", "#22", 22.0):
            with self.subTest(decisao=decisao):
                with self.assertRaises(CadastroRecusado):
                    Tolerancia("20 usos", "provisoria", decisao=decisao)
        t = Tolerancia("20 usos", "provisoria", decisao=22)
        self.assertIs(t.origem, OrigemTolerancia.PROVISORIA)
        self.assertEqual(t.decisao, 22)
        self.assertIs(_verif(tolerancia=t).tolerancia, t)

    def test_provisoria_com_base_e_recusada(self):
        """Com referência, ou com data e método, ela não é provisória: a tela
        mostraria um provisório com cara de literatura ou de serviço."""
        # A lista e os bytes: o ``_texto`` os lia como vazios, e o provisório
        # entrava com a referência dentro.
        for kw in ({"referencia": "TG-142"}, {"data": date(2026, 10, 1)},
                   {"metodo": "TG-218"}, {"referencia": ["TG-142"]},
                   {"metodo": b"TG-218"}):
            with self.subTest(kw=kw):
                with self.assertRaises(CadastroRecusado):
                    Tolerancia("20 usos", "provisoria", decisao=22, **kw)

    def test_item_de_decisao_so_na_provisoria(self):
        """Literatura com item de decisão em aberto: a tela não a marcaria
        provisória, e o número diria que ela é."""
        with self.assertRaises(CadastroRecusado):
            Tolerancia("±3%", "literatura", referencia="TG-142", decisao=6)
        with self.assertRaises(CadastroRecusado):
            Tolerancia("±3%", "servico", data=date(2026, 10, 1),
                       metodo="TG-218", decisao=6)

    def test_tolerancia_que_nao_e_tolerancia_e_recusada(self):
        with self.assertRaises(CadastroRecusado):
            _verif(tolerancia="±3%")

    def test_tolerancia_sem_limite_e_recusada(self):
        with self.assertRaises(CadastroRecusado):
            Tolerancia("", "literatura", referencia="TG-142")


class TestAlertaEIndicador(unittest.TestCase):

    def _nao_conforme(self, estado, origem=Origem.PRODUCAO):
        return _rodar(_verif(lambda d: Avaliacao(Resultado.NAO_CONFORME),
                             estado=estado), origem=origem)

    def test_sombra_executa_e_grava_mas_nao_vira_alerta(self):
        porta = PortaEmMemoria()
        e = executar(_verif(lambda d: Avaliacao(Resultado.NAO_CONFORME)),
                     _entrada(), porta, agora=lambda: AGORA)
        self.assertEqual(porta.execucoes, [e])
        self.assertIs(e.estado, Estado.SOMBRA)
        self.assertFalse(e.vira_alerta)
        self.assertEqual(alertas([e]), [])
        self.assertEqual(para_indicador([e]), [])

    def test_ativa_em_producao_vira_alerta_e_entra_no_indicador(self):
        e = self._nao_conforme("ativa")
        self.assertEqual(alertas([e]), [e])
        self.assertEqual(para_indicador([e]), [e])

    def test_semeado_nao_entra_em_indicador_nem_alerta(self):
        e = self._nao_conforme("ativa", Origem.SEMEADO)
        self.assertIs(e.origem, Origem.SEMEADO)
        self.assertEqual(para_indicador([e]), [])
        self.assertEqual(alertas([e]), [])

    def test_quais_resultados_viram_alerta(self):
        for r in Resultado:
            motivo = "x" if r in v.PEDEM_MOTIVO else ""
            with self.subTest(r=r):
                e = _rodar(_verif(lambda d, r=r, m=motivo: Avaliacao(r, m),
                                  estado="ativa"))
                self.assertEqual(e.vira_alerta, r in (
                    Resultado.NAO_CONFORME, Resultado.INDETERMINADO,
                    Resultado.ERRO))

    def test_a_execucao_guarda_o_estado_do_momento(self):
        # Promover depois não reescreve o passado: a execução de sombra
        # continua sem alerta mesmo que a verificação vire ativa.
        verif = _verif(lambda d: Avaliacao(Resultado.NAO_CONFORME))
        e = _rodar(verif)
        promovida = replace(verif, estado="ativa")
        self.assertIs(promovida.estado, Estado.ATIVA)
        self.assertIs(e.estado, Estado.SOMBRA)
        self.assertFalse(e.vira_alerta)


class TestSemQtBancoRedeNemArquivo(unittest.TestCase):
    """O ``test_arquitetura`` já proíbe Qt, tela, módulo e adaptador no
    ``nucleo/``; esta é a parte que ele não cobre — arquivo e rede."""

    PROIBIDOS = {"os", "pathlib", "io", "socket", "sqlite3", "pyodbc",
                 "psycopg", "psycopg2", "subprocess", "shutil", "urllib",
                 "http", "threading", "logging", "builtins"}

    def test_imports(self):
        arvore = ast.parse(FONTE.read_text(encoding="utf-8"))
        nomes = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                nomes |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes.add(no.module.split(".")[0])
            elif (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                  and no.func.id == "open"):
                nomes.add("builtins")
        self.assertEqual(nomes & self.PROIBIDOS, set())
        self.assertTrue(nomes <= {"__future__", "re", "dataclasses",
                                  "datetime", "enum", "types", "typing"},
                        nomes)


class TestProveniencia(unittest.TestCase):
    """FR-39 sem banco (o mesmo contra o PostgreSQL: ``test_postgres_execucao``).

    Execução ``conforme`` que não diz de que RT Plan nem de que carga do
    ``variandw`` partiu não se sustenta na auditoria: não há como provar que
    o plano conferido é o que foi tratado."""

    SOMA = "a" * 64

    def _falta(self, **kw):
        campos = dict(objeto="plano:1", versao="v1", dados={},
                      degrau="variandw", data="2026-10-27T06:00:00-03:00")
        campos.update(kw)
        return v.falta_proveniencia(Entrada(**campos))

    def test_completas_passam(self):
        for kw in ({}, dict(degrau="dicom", data="", arquivo="RP.dcm",
                            checksum=self.SOMA),
                   dict(arquivo="RP.dcm", checksum=self.SOMA)):
            with self.subTest(kw):
                self.assertEqual(self._falta(**kw), "")

    def test_incompletas_dizem_o_que_falta(self):
        casos = {
            "sem degrau": (dict(degrau=" "), "sem degrau"),
            "degrau inventado": (dict(degrau="manual"), "não existe"),
            "banco sem data": (dict(data=""), "sem a data da carga"),
            "arquivo sem nome": (dict(degrau="esapi_json", data=""),
                                 "sem o arquivo lido"),
            "nome sem hash": (dict(arquivo="RP.dcm"), "andam juntos"),
            "hash sem nome": (dict(checksum=self.SOMA), "andam juntos"),
            "hash maiúsculo": (dict(arquivo="RP.dcm",
                                    checksum=self.SOMA.upper()), "SHA-256"),
            "hash curto": (dict(arquivo="RP.dcm", checksum="abc"), "SHA-256"),
        }
        for nome, (kw, trecho) in casos.items():
            with self.subTest(nome):
                self.assertIn(trecho, self._falta(**kw))

    def test_degraus_batem_com_a_restricao_do_banco(self):
        """Degrau novo só no Python (ou só na migração) faria uma ponta
        aceitar o que a outra recusa, e o motivo legível mentiria."""
        sql = (FONTE.parents[2] / "migracoes" / "0002_execucao.sql").read_text(
            encoding="utf-8")
        for degrau in v.DEGRAUS_DE_BANCO | v.DEGRAUS_DE_ARQUIVO:
            with self.subTest(degrau):
                self.assertIn(f"'{degrau}'", sql)


if __name__ == "__main__":
    unittest.main()
