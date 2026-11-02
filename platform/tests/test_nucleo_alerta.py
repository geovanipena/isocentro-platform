"""Alerta, assinatura, passada da concentradora e pasta da âncora, sem banco (R-21).

O que estes testes guardam:

- prazo que vence no instante exato contado como "ainda em dia" — a borda é
  do vencido (``decisoes-sem-base.md`` #38);
- ``alta`` resolvido sem justificativa, ou alerta resolvido duas vezes (FR-5);
- assinatura de uma versão do plano valendo para outra (AD-30);
- uma fonte de prazos com defeito calando as outras na concentradora;
- a âncora da manhã trocada pela da tarde, ou um arquivo de âncora
  corrompido passando calado pelo verificador (AD-32).
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from isocentro.adaptadores.ancora.pasta import PastaDeAncoras, nome_do_dia
from isocentro.nucleo import alerta, assinatura, concentradora
from isocentro.nucleo.alerta import AlertaRecusado, EstadoAlerta, Prazo
from isocentro.nucleo.assinatura import Assinatura
from isocentro.nucleo.integridade import Ancora
from isocentro.nucleo.verificacao import Severidade

BRT = timezone(timedelta(hours=-3))
VENCE = datetime(2026, 11, 1, 8, 0, tzinfo=BRT)


def _prazo(**kw):
    campos = dict(chave="documentacao.aso:17:2026-11-01", objeto="aso:17",
                  clinica="CEL", responsavel="fisico",
                  motivo="ASO vence em 01/11/2026",
                  aviso_em=VENCE - timedelta(days=30), vence_em=VENCE)
    campos.update(kw)
    return Prazo(**campos)


class TestPrazo(unittest.TestCase):

    def test_borda_e_do_vencido(self):
        p = _prazo()
        self.assertIsNone(alerta.severidade_do_prazo(
            p, VENCE - timedelta(days=31)))
        self.assertIs(alerta.severidade_do_prazo(
            p, VENCE - timedelta(days=30)), Severidade.ATENCAO)
        self.assertIs(alerta.severidade_do_prazo(
            p, VENCE - timedelta(microseconds=1)), Severidade.ATENCAO)
        self.assertIs(alerta.severidade_do_prazo(p, VENCE), Severidade.ALTA)

    def test_fuso_diferente_e_o_mesmo_instante(self):
        """A concentradora pode devolver a hora em UTC e o módulo dar o prazo
        em Brasília: comparar o relógio de parede adiantaria o alerta 3 h."""
        self.assertIs(alerta.severidade_do_prazo(
            _prazo(), datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc)),
            Severidade.ALTA)
        self.assertIs(alerta.severidade_do_prazo(
            _prazo(), datetime(2026, 11, 1, 10, 59, tzinfo=timezone.utc)),
            Severidade.ATENCAO)

    def test_hora_sem_fuso_recusada(self):
        with self.assertRaises(AlertaRecusado):
            _prazo(vence_em=datetime(2026, 11, 1, 8, 0))
        with self.assertRaises(AlertaRecusado):
            alerta.severidade_do_prazo(_prazo(), datetime(2026, 11, 1))

    def test_prazo_mal_formado_recusado(self):
        for kw in ({"clinica": "DUO"}, {"chave": "aso:17"}, {"motivo": " "},
                   {"aviso_em": VENCE + timedelta(days=1)}):
            with self.subTest(kw=kw), self.assertRaises(AlertaRecusado):
                _prazo(**kw)


class TestCicloDeVida(unittest.TestCase):

    def test_estado_pelos_eventos(self):
        self.assertIs(alerta.estado([]), EstadoAlerta.ABERTO)
        self.assertIs(alerta.estado(["visto", "visto"]), EstadoAlerta.VISTO)
        self.assertIs(alerta.estado(["visto", "resolvido"]),
                      EstadoAlerta.RESOLVIDO)

    def test_resolver_alta_pede_justificativa(self):
        for vazia in (None, "", "   "):
            with self.subTest(vazia=vazia), self.assertRaises(AlertaRecusado):
                alerta.conferir_evento("alta", [], "resolvido", vazia)
        self.assertEqual(alerta.conferir_evento(
            "alta", [], "resolvido", " plano refeito "), "plano refeito")
        self.assertIsNone(alerta.conferir_evento(
            "atencao", [], "resolvido", None))

    def test_nada_depois_de_resolvido(self):
        with self.assertRaises(AlertaRecusado):
            alerta.conferir_evento("atencao", ["resolvido"], "visto", None)

    def test_ordem_severidade_e_prazo(self):
        t = datetime(2026, 10, 28, 8, 0, tzinfo=BRT)

        def a(nome, sev, vence=None, quando=t):
            return SimpleNamespace(nome=nome, severidade=sev, vence_em=vence,
                                   quando=quando)
        fila = alerta.ordenar([
            a("info", "informativo"),
            a("atencao_sem_prazo", "atencao"),
            a("alta_execucao", "alta", quando=t - timedelta(hours=1)),
            a("alta_vence_depois", "alta", t + timedelta(days=2)),
            a("alta_vence_antes", "alta", t + timedelta(days=1)),
            a("atencao_prazo", "atencao", t + timedelta(days=9)),
        ])
        self.assertEqual([x.nome for x in fila], [
            "alta_vence_antes", "alta_vence_depois", "alta_execucao",
            "atencao_prazo", "atencao_sem_prazo", "info"])


def _assinatura(versao, minuto=0):
    return Assinatura("1", "plano.duplo_check", "9000001/C1/Plano1", versao,
                      "fisico", "fulano",
                      datetime(2026, 10, 28, 9, minuto, tzinfo=BRT))


class TestAssinatura(unittest.TestCase):

    def test_versao_do_plano_vazia_se_falta_parte(self):
        self.assertEqual(assinatura.versao_do_plano(
            12, "1.2.3", "2026-10-23T08:00:00", "Approved"),
            "12|1.2.3|2026-10-23T08:00:00|Approved")
        for faltando in ((None, "1.2", "h", "s"), (12, "", "h", "s"),
                         (12, "1.2", None, "s"), (True, "1.2", "h", "s")):
            with self.subTest(faltando=faltando):
                self.assertEqual(assinatura.versao_do_plano(*faltando), "")

    def test_versao_nova_volta_a_pendente(self):
        """O plano reotimizado depois do Duplo Check não é o que o segundo
        físico conferiu (FR-8)."""
        assinaturas = [_assinatura("v1")]
        self.assertTrue(assinatura.situacao(assinaturas, "v1").assinado)
        pendente = assinatura.situacao(assinaturas, "v2")
        self.assertFalse(pendente.assinado)
        self.assertIn("v1", pendente.motivo)

    def test_sem_versao_atual_e_pendente(self):
        self.assertFalse(assinatura.situacao([_assinatura("v1")], "").assinado)


class _Ponta:
    def __init__(self, ancora):
        self._ancora = ancora

    def agora(self):
        return datetime(2026, 10, 28, 23, 50, tzinfo=BRT)

    def ponta(self):
        return self._ancora


class _Alertas:
    def __init__(self):
        self.recebidos = []

    def abrir_do_prazo(self, prazo, agora):
        self.recebidos.append(prazo.chave)
        return alerta.severidade_do_prazo(prazo, agora)


class TestPassada(unittest.TestCase):

    def test_fonte_com_defeito_nao_cala_as_outras(self):
        def quebrada():
            raise RuntimeError("tabela sumiu")
        alertas = _Alertas()
        rel = concentradora.passada(
            {"qualidade": quebrada, "documentacao": lambda: [_prazo()]},
            alertas, _Ponta(None), guarda=None)
        self.assertEqual(alertas.recebidos, ["documentacao.aso:17:2026-11-01"])
        self.assertEqual(rel.alertas, [Severidade.ATENCAO])
        self.assertTrue(any(f.startswith("qualidade:") for f in rel.falhas))

    def test_sem_pasta_da_ancora_a_falta_aparece(self):
        rel = concentradora.passada({}, _Alertas(), _Ponta(Ancora(3, b"x" * 32)),
                                    guarda=None)
        self.assertIn("âncora: pasta da âncora não configurada", rel.falhas)

    def test_dia_da_ancora_e_o_local(self):
        """23h50 em Brasília já é dia 29 em UTC: a âncora tem de cair no
        arquivo do dia em que a clínica viveu aquele log."""
        dias = []

        class Guarda:
            def gravar_do_dia(self, ancora, dia, quando):
                dias.append(dia)
                return True
        concentradora.passada({}, _Alertas(), _Ponta(Ancora(3, b"x" * 32)),
                              Guarda())
        self.assertEqual(len(dias), 1)
        self.assertEqual(dias[0], _Ponta(None).agora().astimezone().date())


class TestPastaDeAncoras(unittest.TestCase):

    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp(prefix="ancora_"))
        self.addCleanup(shutil.rmtree, self.pasta, True)
        self.guarda = PastaDeAncoras(self.pasta)
        self.quando = datetime(2026, 10, 28, 6, 0, tzinfo=BRT)

    def test_a_ancora_do_dia_nao_e_reescrita(self):
        dia = date(2026, 10, 28)
        self.assertTrue(self.guarda.gravar_do_dia(
            Ancora(5, bytes(range(32))), dia, self.quando))
        self.assertFalse(self.guarda.gravar_do_dia(
            Ancora(9, bytes(32)), dia, self.quando))
        ancoras, problemas = self.guarda.ler()
        self.assertEqual(ancoras, [Ancora(5, bytes(range(32)))])
        self.assertEqual(problemas, [])

    def test_arquivo_corrompido_e_problema_e_nao_silencio(self):
        (self.pasta / nome_do_dia(date(2026, 10, 27))).write_text(
            "cinco abc\n", encoding="ascii")
        (self.pasta / "LEIA-ME.txt").write_text("outra coisa", encoding="ascii")
        ancoras, problemas = self.guarda.ler()
        self.assertEqual(ancoras, [])
        self.assertEqual(len(problemas), 1)
        self.assertIn("2026-10-27", problemas[0])


if __name__ == "__main__":
    unittest.main()
