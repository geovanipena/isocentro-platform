"""O motor gravando no PostgreSQL: execução vigente, proveniência e o JSON ESAPI (R-20).

O que estes testes guardam, contra o banco de verdade (AD-34):

- a concentradora e a estação rodando a mesma verificação no mesmo plano
  gerando DUAS execuções vigentes — e daí dois alertas do mesmo fato (AD-28);
- execução gravada sem dizer de que RT Plan ou de que carga do ``variandw``
  partiu, que não se sustenta na auditoria (FR-39);
- o resultado ESAPI chegando ao banco por um caminho diferente do avaliador
  Python, ou um JSON quebrado sumindo sem execução (CAP-9).
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timedelta, timezone

from isocentro.adaptadores.esapi_json.importacao import (
    ImportacaoRecusada, importar)
from isocentro.adaptadores.postgres.execucoes import PortaDeExecucoes
from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo.gravacao import GravacaoRecusada, gravar
from isocentro.nucleo.verificacao import (
    Avaliacao, Entrada, Origem, Resultado, Verificacao, executar)
from tests.pg_teste import ComBanco, precisa_do_postgres
from tests.test_esapi_json import HASH, VALIDADO, _doc

CARGA = "2026-10-27T06:00:00-03:00"
INICIO = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
PLANO = "9000001/C1/Plano1"
VERSAO_PLANO = "2026-10-23T08:00:00"


def _verif(resultado=Resultado.CONFORME, motivo="", **kw):
    campos = dict(id="plano.fracoes", versao="1.0.0",
                  regra="nº de frações do plano = prescrição",
                  fontes=("fichas/atividades/C05.md",), gatilho="evento",
                  responsavel="fisico", severidade="alta", estado="ativa",
                  avaliador=lambda _d: Avaliacao(resultado, motivo,
                                                 {"fracoes": 25}))
    campos.update(kw)
    return Verificacao(**campos)


def _entrada(**kw):
    campos = dict(objeto=PLANO, versao=VERSAO_PLANO, dados={"fracoes": 25},
                  degrau="variandw", data=CARGA)
    campos.update(kw)
    return Entrada(**campos)


class _Relogio:
    def __init__(self):
        self.agora = INICIO

    def __call__(self):
        self.agora += timedelta(minutes=1)
        return self.agora


@precisa_do_postgres
class TestExecucaoVigente(ComBanco):

    def setUp(self):
        super().setUp()
        self.execucoes = PortaDeExecucoes(self.app, "isocentro_concentradora")
        self.relogio = _Relogio()

    def _executar(self, verif=None, entrada=None, origem=Origem.PRODUCAO):
        executar(verif or _verif(), entrada or _entrada(), self.execucoes,
                 origem=origem, agora=self.relogio)
        return self.execucoes.vigente(
            "plano.fracoes", Origem(origem).value,
            (entrada or _entrada()).objeto, (entrada or _entrada()).versao)

    def test_grava_com_proveniencia_e_linha_de_log(self):
        v = self._executar()
        self.assertEqual((v.resultado, v.degrau, v.data_origem, v.evidencia),
                         ("conforme", "variandw", CARGA, {"fracoes": 25}))
        with self.banco.conectar() as c:
            log = c.execute("SELECT quem, modulo, tabela, registro, versao_origem"
                            " FROM nucleo.log").fetchall()
        self.assertEqual(log, [("isocentro_concentradora", "nucleo",
                                "nucleo.execucao", v.id, VERSAO_PLANO)])

    def test_repetir_igual_nao_grava_de_novo(self):
        """A varredura roda a cada poucos minutos: sem isto, uma linha de log
        por varredura, e a mesma conclusão "nova" a cada vez."""
        primeira = self._executar()
        for _ in range(3):
            self.assertEqual(self._executar().id, primeira.id)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.execucao"), 1)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 1)

    def test_resultado_novo_substitui_e_o_anterior_fica(self):
        antes = self._executar(_verif(Resultado.INDETERMINADO, "sem prescrição"))
        depois = self._executar(entrada=_entrada(data="2026-10-28T06:00:00-03:00"))
        self.assertNotEqual(antes.id, depois.id)
        historico = self.execucoes.historico("plano.fracoes", "producao",
                                             PLANO, VERSAO_PLANO)
        self.assertEqual([h.resultado for h in historico],
                         ["indeterminado", "conforme"])
        with self.banco.conectar() as c:
            self.assertEqual(c.execute(
                "SELECT substitui FROM nucleo.log WHERE registro = %s",
                (depois.id,)).fetchone()[0], antes.id)

    def test_carga_nova_com_o_mesmo_resultado_tambem_substitui(self):
        """A proveniência faz parte da execução: a vigente tem de dizer de
        que carga do ``variandw`` partiu a ÚLTIMA conferência (FR-39)."""
        antes = self._executar()
        depois = self._executar(entrada=_entrada(data="2026-10-28T06:00:00-03:00"))
        self.assertNotEqual(antes.id, depois.id)
        self.assertEqual(depois.data_origem, "2026-10-28T06:00:00-03:00")

    def test_outra_versao_do_plano_e_outra_chave(self):
        v1 = self._executar()
        v2 = self._executar(entrada=_entrada(versao="2026-10-27T09:00:00"))
        self.assertNotEqual(v1.id, v2.id)
        self.assertEqual(self.execucoes.vigente(
            "plano.fracoes", "producao", PLANO, VERSAO_PLANO).id, v1.id)

    def test_semeado_nao_substitui_producao(self):
        """Erro semeado (CAP-11) gravado por cima da execução real faria o
        plano de verdade perder a conferência que teve."""
        real = self._executar()
        semeado = self._executar(_verif(Resultado.NAO_CONFORME),
                                 origem=Origem.SEMEADO)
        self.assertNotEqual(real.id, semeado.id)
        self.assertEqual(self.execucoes.vigente(
            "plano.fracoes", "producao", PLANO, VERSAO_PLANO).resultado,
            "conforme")

    def test_avaliador_que_estoura_grava_erro_com_motivo(self):
        def estoura(_d):
            raise ZeroDivisionError("divisão por zero")
        v = self._executar(_verif(avaliador=estoura))
        self.assertEqual((v.resultado, v.motivo),
                         ("erro", "ZeroDivisionError: divisão por zero"))

    def test_duas_pontas_ao_mesmo_tempo_deixam_uma_vigente(self):
        """Estação e concentradora sobre o mesmo plano, alternando resultado:
        sem a trava por chave, as duas achavam "nenhuma vigente" e gravavam
        duas execuções novas, ambas vigentes."""
        erros = []

        def ponta(papel, resultado):
            try:
                with self.banco.conectar(papel) as c:
                    porta = PortaDeExecucoes(c, papel)
                    for _ in range(10):
                        executar(_verif(resultado, "x"), _entrada(), porta)
            except Exception as erro:  # noqa: BLE001 - relatado no assert abaixo
                erros.append(erro)

        pontas = [threading.Thread(target=ponta, args=a) for a in (
            ("isocentro_app", Resultado.NAO_CONFORME),
            ("isocentro_concentradora", Resultado.INDETERMINADO))]
        for t in pontas:
            t.start()
        for t in pontas:
            t.join(timeout=120)
        self.assertEqual(erros, [])
        # ``vigente`` levanta se houver mais de uma.
        self.assertIsNotNone(self.execucoes.vigente(
            "plano.fracoes", "producao", PLANO, VERSAO_PLANO))


@precisa_do_postgres
class TestProveniencia(ComBanco):
    """FR-39: a execução sem proveniência não é gravada."""

    RT_PLAN = "RP.1.2.840.113619.2.1.dcm"
    SOMA = hashlib.sha256(b"rt plan ficticio").hexdigest()

    def setUp(self):
        super().setUp()
        self.execucoes = PortaDeExecucoes(self.app, "geovani.pena")

    def test_recusadas_e_nada_gravado(self):
        casos = {
            "sem degrau": dict(degrau=""),
            "degrau inventado": dict(degrau="ARIA"),
            "variandw sem a data da carga": dict(data=""),
            "dicom sem o arquivo": dict(degrau="dicom", data=""),
            "arquivo sem checksum": dict(degrau="dicom", arquivo=self.RT_PLAN),
            "checksum sem arquivo": dict(checksum=self.SOMA),
            "checksum que não é SHA-256": dict(degrau="dicom",
                                                arquivo=self.RT_PLAN,
                                                checksum="abc"),
            "checksum em maiúsculas": dict(degrau="dicom", arquivo=self.RT_PLAN,
                                           checksum=self.SOMA.upper()),
        }
        for nome, kw in casos.items():
            with self.subTest(nome):
                with self.assertRaises(GravacaoRecusada):
                    executar(_verif(), _entrada(**kw), self.execucoes)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.execucao"), 0)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 0)

    def test_rt_plan_com_checksum_e_carga_grava(self):
        executar(_verif(), _entrada(degrau="dicom", arquivo=self.RT_PLAN,
                                    checksum=self.SOMA), self.execucoes)
        v = self.execucoes.vigente("plano.fracoes", "producao", PLANO,
                                   VERSAO_PLANO)
        self.assertEqual((v.arquivo, v.checksum, v.data_origem),
                         (self.RT_PLAN, self.SOMA, CARGA))

    def test_o_banco_recusa_quem_pula_o_python(self):
        """Pelo ``nucleo.gravar`` direto, sem a ``PortaDeExecucoes``: a
        restrição da tabela é a garantia, não a conferência do Python."""
        linha = dict(verificacao_id="plano.fracoes", verificacao_versao="1.0.0",
                     estado="ativa", severidade="alta", origem="producao",
                     objeto=PLANO, objeto_versao=VERSAO_PLANO, degrau="dicom",
                     resultado="conforme", motivo="", evidencia="{}",
                     quando=INICIO)
        with self.assertRaises(GravacaoRecusada) as ctx:
            gravar(PortaPostgres(self.app), modulo="nucleo",
                   tabela="nucleo.execucao", dados=linha, quem="geovani.pena")
        self.assertIn("execucao_degrau_de_arquivo_com_arquivo",
                      str(ctx.exception))
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.execucao"), 0)


@precisa_do_postgres
class TestImportacaoEsapi(ComBanco):
    """CAP-9: o JSON vira execução pelo mesmo motor, com o arquivo e o hash."""

    ARQUIVO = "plano.fracoes_9000001_Plano1.json"

    def setUp(self):
        super().setUp()
        self.execucoes = PortaDeExecucoes(self.app, "isocentro_concentradora")
        self.catalogo = {"plano.fracoes": _verif()}

    def _importar(self, conteudo, atual=VERSAO_PLANO, inventario=None):
        if isinstance(conteudo, str):
            conteudo = conteudo.encode("utf-8")
        return importar(conteudo, arquivo=self.ARQUIVO, catalogo=self.catalogo,
                        versao_atual=lambda _objeto: atual,
                        inventario=VALIDADO if inventario is None else inventario,
                        porta=self.execucoes)

    def _vigente(self, versao=VERSAO_PLANO):
        return self.execucoes.vigente("plano.fracoes", "producao", PLANO, versao)

    def test_json_valido_grava_o_resultado_com_arquivo_e_hash(self):
        conteudo = _doc().encode("utf-8")
        self._importar(conteudo)
        v = self._vigente()
        self.assertEqual((v.resultado, v.evidencia, v.degrau, v.arquivo),
                         ("conforme", {"fracoes": 25}, "esapi_json",
                          self.ARQUIVO))
        self.assertEqual(v.checksum, hashlib.sha256(conteudo).hexdigest())

    def test_reimportar_o_mesmo_arquivo_nao_grava_de_novo(self):
        self._importar(_doc())
        self._importar(_doc())
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.execucao"), 1)

    def test_plano_que_mudou_vira_indeterminado_na_versao_atual(self):
        """O script avaliou a versão de 23/10; o plano de hoje é outro. O
        ``indeterminado`` cai na chave do plano ATUAL, onde alguém olha."""
        self._importar(_doc(), atual="2026-10-27T09:00:00")
        v = self._vigente("2026-10-27T09:00:00")
        self.assertEqual(v.resultado, "indeterminado")
        self.assertIn("a atual é 2026-10-27T09:00:00", v.motivo)
        self.assertIsNone(self._vigente())

    def test_script_fora_do_inventario_vira_indeterminado(self):
        self._importar(_doc(), inventario={})
        self.assertEqual(self._vigente().resultado, "indeterminado")

    def test_json_quebrado_que_diz_o_plano_vira_erro_gravado(self):
        self._importar(_doc(versao_esquema=99))
        v = self._vigente()
        self.assertEqual(v.resultado, "erro")
        self.assertIn("versão de esquema 99 desconhecida", v.motivo)

    def test_sem_como_atribuir_nao_ha_execucao(self):
        casos = {
            "não é JSON": b"\xff\xfe nada",
            "sem plano": b'{"verificacao": "plano.fracoes"}',
            "verificação fora do catálogo": _doc(verificacao="plano.outra"),
        }
        for nome, conteudo in casos.items():
            with self.subTest(nome):
                with self.assertRaises(ImportacaoRecusada):
                    self._importar(conteudo)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.execucao"), 0)

    def test_hash_da_dll_do_inventario_e_o_do_json(self):
        """Guarda contra o ``VALIDADO`` dos testes deixar de bater com o
        ``_doc``: o caminho inteiro até ``conforme`` depende dos dois."""
        self.assertEqual(VALIDADO["teste.ficticio"].hash_dll, HASH)
