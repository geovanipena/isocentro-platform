"""Alerta, assinatura, concentradora e âncora contra o PostgreSQL de verdade (R-21).

O que estes testes guardam:

- prazo que vence com o app fechado só aparecendo quando alguém abre e
  calcula — ou nem aparecendo (FR-41, CAP-14);
- dois alertas do mesmo fato, ou alerta de um resultado que já não é o
  vigente (AD-28);
- "visto" e "resolvido" sobrescrevendo o alerta, ou resolvidos sem dizer
  quem (AD-29); ``alta`` resolvido sem justificativa (FR-5);
- assinatura em nome de outro, ou valendo para outra versão do plano (AD-30);
- linha do log alterada depois da âncora do dia sem ninguém apontar
  registro e posição (AD-32).
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from isocentro.adaptadores.ancora.pasta import PastaDeAncoras
from isocentro.adaptadores.postgres.alertas import PortaDeAlertas
from isocentro.adaptadores.postgres.assinaturas import PortaDeAssinaturas
from isocentro.adaptadores.postgres.execucoes import PortaDeExecucoes
from isocentro.adaptadores.postgres.porta import PortaPostgres
from isocentro.nucleo import concentradora
from isocentro.nucleo.alerta import CLINICAS, AlertaRecusado, Prazo
from isocentro.nucleo.assinatura import versao_do_plano
from isocentro.nucleo.gravacao import GravacaoRecusada, gravar
from isocentro.nucleo.integridade import verificar
from isocentro.nucleo.verificacao import Resultado, executar
from tests.pg_teste import ComBanco, precisa_do_postgres
from tests.test_postgres_execucao import PLANO, _entrada, _Relogio, _verif


def _prazo(agora, *, vence=timedelta(hours=-1), aviso=timedelta(days=-30),
           clinica="CEL", chave="documentacao.aso:17"):
    return Prazo(chave=chave, objeto="aso:17", clinica=clinica,
                 responsavel="fisico", motivo="ASO vencido",
                 aviso_em=agora + vence + aviso, vence_em=agora + vence)


@precisa_do_postgres
class TestPrazoComAppFechado(ComBanco):

    def setUp(self):
        super().setUp()
        # A concentradora é outra conexão, com o papel dela: nada da estação
        # está aberto enquanto ela roda.
        self.conc = self.banco.conectar("isocentro_concentradora")
        self.addCleanup(self.conc.close)
        self.agora = PortaPostgres(self.conc).agora()
        self.pasta = Path(tempfile.mkdtemp(prefix="ancora_"))
        self.addCleanup(shutil.rmtree, self.pasta, True)

    def _passada(self, *prazos):
        return concentradora.passada(
            {"documentacao": lambda: list(prazos)},
            PortaDeAlertas(self.conc, "isocentro_concentradora"),
            PortaPostgres(self.conc), PastaDeAncoras(self.pasta))

    def test_prazo_vencido_com_app_fechado_e_alta_na_abertura(self):
        """O pronto-quando da R-21: o prazo venceu de madrugada, a
        concentradora rodou sozinha, e a primeira pessoa que abre o app
        encontra o alerta ``alta`` na fila."""
        rel = self._passada(_prazo(self.agora))
        self.assertEqual(rel.falhas, [])
        fila = PortaDeAlertas(self.app, "geovani.pena").abertos(CLINICAS)
        self.assertEqual([(a.severidade, a.objeto, a.estado.value)
                          for a in fila], [("alta", "aso:17", "aberto")])
        self.assertEqual(self._conta(
            "SELECT quem FROM nucleo.log WHERE tabela = 'nucleo.alerta'"),
            "isocentro_concentradora")

    def test_passada_repetida_nao_duplica(self):
        for _ in range(3):
            self._passada(_prazo(self.agora))
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.alerta"), 1)

    def test_vencido_substitui_o_aviso(self):
        """O aviso fica no histórico e sai da fila: dois alertas do mesmo
        ASO, um ``atencao`` e um ``alta``, diriam que são duas coisas."""
        self._passada(_prazo(self.agora, vence=timedelta(days=5)))
        fila = PortaDeAlertas(self.app, "x").abertos(CLINICAS)
        self.assertEqual([a.severidade for a in fila], ["atencao"])
        aviso = fila[0].id
        self._passada(_prazo(self.agora))   # agora vencido
        fila = PortaDeAlertas(self.app, "x").abertos(CLINICAS)
        self.assertEqual([a.severidade for a in fila], ["alta"])
        self.assertEqual(self._conta(
            "SELECT substitui FROM nucleo.log WHERE tabela = 'nucleo.alerta'"
            " AND substitui IS NOT NULL"), aviso)

    def test_em_dia_nao_abre(self):
        rel = self._passada(_prazo(self.agora, vence=timedelta(days=60)))
        self.assertEqual(rel.alertas, [])
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.alerta"), 0)

    def test_clinica_do_objeto(self):
        """O alerta da BET não aparece na fila de quem só vê a CEL; o físico
        responsável, que vê as três, vê os dois."""
        self._passada(_prazo(self.agora, clinica="BET", chave="documentacao.a:1"),
                      _prazo(self.agora, clinica="CEL", chave="documentacao.a:2"))
        porta = PortaDeAlertas(self.app, "x")
        self.assertEqual([a.clinica for a in porta.abertos(["CEL"])], ["CEL"])
        self.assertEqual(len(porta.abertos(CLINICAS)), 2)
        self.assertEqual(porta.abertos(CLINICAS, responsaveis=["medico"]), [])


@precisa_do_postgres
class TestCicloDeVida(ComBanco):

    def setUp(self):
        super().setUp()
        conc = self.banco.conectar("isocentro_concentradora")
        self.addCleanup(conc.close)
        agora = PortaPostgres(conc).agora()
        PortaDeAlertas(conc, "isocentro_concentradora").abrir_do_prazo(
            _prazo(agora), agora)
        self.fulano = PortaDeAlertas(self.app, "fulano")
        self.alerta = self.fulano.abertos(CLINICAS)[0]

    def test_visto_e_resolvido_sao_eventos_com_autor(self):
        self.fulano.ver(self.alerta.id)
        PortaDeAlertas(self.app, "beltrano").ver(self.alerta.id)
        visto = self.fulano.abertos(CLINICAS)[0]
        self.assertEqual(visto.estado.value, "visto")
        self.assertEqual([q for q, _ in visto.vistos], ["fulano", "beltrano"])
        resolvido = self.fulano.resolver(self.alerta.id, "ASO renovado")
        self.assertEqual(resolvido.estado.value, "resolvido")
        self.assertEqual(self.fulano.abertos(CLINICAS), [])
        # O alerta em si não mudou uma vírgula: só se acrescentou (AD-29).
        self.assertEqual(self._conta(
            "SELECT count(*) FROM nucleo.alerta_evento"), 3)

    def test_alta_sem_justificativa_recusado(self):
        with self.assertRaises(AlertaRecusado):
            self.fulano.resolver(self.alerta.id)
        self.assertEqual(self._conta(
            "SELECT count(*) FROM nucleo.alerta_evento"), 0)

    def test_o_banco_recusa_quem_pula_o_python(self):
        porta = PortaPostgres(self.app)
        with self.assertRaises(GravacaoRecusada) as ctx:
            gravar(porta, modulo="nucleo", tabela="nucleo.alerta_evento",
                   quem="fulano", dados={"alerta_id": int(self.alerta.id),
                                         "evento": "resolvido"})
        self.assertIn("justificativa", str(ctx.exception))
        gravar(porta, modulo="nucleo", tabela="nucleo.alerta_evento",
               quem="fulano", dados={"alerta_id": int(self.alerta.id),
                                     "evento": "resolvido",
                                     "justificativa": "feito"})
        with self.assertRaises(GravacaoRecusada) as ctx:
            gravar(porta, modulo="nucleo", tabela="nucleo.alerta_evento",
                   quem="fulano", dados={"alerta_id": int(self.alerta.id),
                                         "evento": "visto"})
        self.assertIn("já foi resolvido", str(ctx.exception))

    def test_resolver_duas_vezes_recusado(self):
        self.fulano.resolver(self.alerta.id, "feito")
        with self.assertRaises(AlertaRecusado):
            self.fulano.resolver(self.alerta.id, "de novo")

    def test_app_nao_edita_o_alerta(self):
        import psycopg
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            self.app.execute("UPDATE nucleo.alerta SET severidade = 'informativo'")


@precisa_do_postgres
class TestAlertaDaExecucao(ComBanco):

    def setUp(self):
        super().setUp()
        self.execucoes = PortaDeExecucoes(self.app, "isocentro_concentradora")
        self.alertas = PortaDeAlertas(self.app, "isocentro_concentradora")
        self.relogio = _Relogio()

    def _gravar(self, verif, entrada=None):
        e = entrada or _entrada()
        executar(verif, e, self.execucoes, agora=self.relogio)
        return self.execucoes.vigente(verif.id, "producao", e.objeto, e.versao)

    def _abrir(self, execucao):
        return self.alertas.abrir_da_execucao(execucao, clinica="CEL",
                                              responsavel="fisico")

    def test_nao_conforme_ativo_abre_uma_vez(self):
        ex = self._gravar(_verif(Resultado.NAO_CONFORME))
        primeiro = self._abrir(ex)
        self.assertEqual((primeiro.severidade, primeiro.objeto),
                         ("alta", PLANO))
        self.assertIn("plano.fracoes", primeiro.motivo)
        self.assertEqual(self._abrir(ex).id, primeiro.id)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.alerta"), 1)

    def test_sombra_e_conforme_nao_abrem(self):
        self.assertIsNone(self._abrir(self._gravar(_verif())))
        sombra = _verif(Resultado.NAO_CONFORME, estado="sombra",
                        id="plano.sombra")
        self.assertIsNone(self._abrir(self._gravar(sombra)))

    def test_execucao_substituida_tira_o_alerta_da_fila(self):
        """O plano foi reavaliado e deu ``conforme``: o alerta do resultado
        antigo sai da fila sozinho (AD-28), sem alguém resolver o que já não
        vale."""
        self._abrir(self._gravar(_verif(Resultado.NAO_CONFORME)))
        self.assertEqual(len(self.alertas.abertos(CLINICAS)), 1)
        self._gravar(_verif())
        self.assertEqual(self.alertas.abertos(CLINICAS), [])


@precisa_do_postgres
class TestAssinatura(ComBanco):

    VERSAO = versao_do_plano(12, "1.2.840.1", "2026-10-23T08:00:00", "Approved")

    def test_assina_como_a_sessao_e_vale_so_para_a_versao(self):
        porta = PortaDeAssinaturas(self.app, "fulano")
        a = porta.assinar("plano.duplo_check", PLANO, self.VERSAO, "fisico")
        self.assertEqual((a.pessoa, a.perfil, a.objeto_versao),
                         ("fulano", "fisico", self.VERSAO))
        self.assertTrue(porta.situacao("plano.duplo_check", PLANO,
                                       self.VERSAO).assinado)
        nova = versao_do_plano(12, "1.2.840.2", "2026-10-24T08:00:00",
                               "Approved")
        situacao = porta.situacao("plano.duplo_check", PLANO, nova)
        self.assertFalse(situacao.assinado)
        self.assertIn("mudou", situacao.motivo)
        self.assertEqual(self._conta(
            "SELECT versao_origem FROM nucleo.log"
            " WHERE tabela = 'nucleo.assinatura'"), self.VERSAO)

    def test_sem_versao_nao_assina(self):
        porta = PortaDeAssinaturas(self.app, "fulano")
        with self.assertRaises(GravacaoRecusada):
            porta.assinar("plano.duplo_check", PLANO,
                          versao_do_plano(12, "", "h", "s"), "fisico")
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.assinatura"), 0)


@precisa_do_postgres
class TestAncora(ComBanco):

    def setUp(self):
        super().setUp()
        self.conc = self.banco.conectar("isocentro_concentradora")
        self.addCleanup(self.conc.close)
        self.pasta = Path(tempfile.mkdtemp(prefix="ancora_"))
        self.addCleanup(shutil.rmtree, self.pasta, True)
        self.guarda = PastaDeAncoras(self.pasta)

    def _passada(self):
        return concentradora.passada(
            {}, PortaDeAlertas(self.conc, "isocentro_concentradora"),
            PortaPostgres(self.conc), self.guarda)

    def _adulterar(self, *comandos):
        with self.banco.conectar() as c:
            c.execute("ALTER TABLE nucleo.log DISABLE TRIGGER log_imutavel")
            for comando in comandos:
                c.execute(comando)
            c.execute("ALTER TABLE nucleo.log ENABLE TRIGGER log_imutavel")

    def test_uma_ancora_por_dia(self):
        gravados = [self._gravar(str(i)) for i in range(3)]
        primeira = self._passada()
        self.assertTrue(primeira.ancora_gravada)
        self.assertEqual(primeira.ancora.posicao, gravados[-1].posicao)
        self._gravar("depois")
        self.assertFalse(self._passada().ancora_gravada)
        self.assertEqual(len(list(self.pasta.iterdir())), 1)

    def test_log_vazio_nao_grava_ancora(self):
        rel = self._passada()
        self.assertIsNone(rel.ancora)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_linha_alterada_depois_da_ancora_e_apontada(self):
        """Do pronto-quando: o verificador, com as âncoras da pasta, aponta
        registro e posição da linha mexida depois de a âncora ser gravada."""
        gravados = [self._gravar(str(i)) for i in range(5)]
        self._passada()
        self._gravar("depois da ancora")
        self._adulterar("UPDATE nucleo.log SET quem = 'outra pessoa'"
                        " WHERE posicao = 2")
        ancoras, problemas = self.guarda.ler()
        self.assertEqual(problemas, [])
        achados = verificar(self.porta.linhas_do_log(), ancoras)
        self.assertEqual([(d.posicao, d.registro) for d in achados],
                         [(2, gravados[1].registro)])

    def test_corrente_refeita_so_a_ancora_da_pasta_pega(self):
        for i in range(5):
            self._gravar(str(i))
        self._passada()
        refazer = ["UPDATE nucleo.log SET quem = 'outra pessoa'"
                   " WHERE posicao = 2"]
        for p in range(2, 6):
            if p > 2:
                refazer.append(
                    f"UPDATE nucleo.log SET hash_anterior = (SELECT hash FROM"
                    f" nucleo.log WHERE posicao = {p - 1}) WHERE posicao = {p}")
            refazer.append(
                f"UPDATE nucleo.log l SET hash = nucleo.hash_da_linha(l)"
                f" WHERE posicao = {p}")
        self._adulterar(*refazer)
        linhas = self.porta.linhas_do_log()
        self.assertEqual(verificar(linhas), [])
        ancoras, _ = self.guarda.ler()
        self.assertEqual([d.posicao for d in verificar(linhas, ancoras)], [5])
