"""As partes do PPR vivo no PostgreSQL de verdade (R-85, etapa 2).

O que estes testes guardam:

- importar a semente duas vezes e ficar com dois textos vigentes da mesma
  parte;
- texto corrigido na semente sobrescrevendo o anterior, em vez de entrar
  como registro novo que o substitui (AD-5);
- um módulo gravando a parte de outro (AD-3);
- a parte de uma clínica aparecendo "com dado" em outra.
"""
from __future__ import annotations

import copy
import unittest

from isocentro.adaptadores.postgres import ppr as pg_ppr
from isocentro.dominio import ppr
from isocentro.nucleo.gravacao import GravacaoRecusada
from tests.pg_teste import ComBanco, precisa_do_postgres
from tools import importar_ppr

SEMENTE = {
    "clinica": "ANA",
    "documento": {"arquivo": "fonte/PPR_DUO_JAN25.pdf"},
    "condicoes": [],
    "partes": {
        "identificacao": {"modulo": "fundacao", "texto": "Rua X",
                          "documentos": [], "fonte": "PPR, p. 9"},
        "anexo/estrutura": {"modulo": "fundacao", "texto": "",
                            "documentos": [{"titulo": "Organograma"}],
                            "fonte": ""},
        "gq_riscos": {"modulo": "seguranca", "texto": "SEVRRA",
                      "documentos": [], "fonte": "PPR, p. 12"},
    },
    "dados": {"qualidade": {"equipamentos": [{"nome": "VitalBeam"}]}},
}


@precisa_do_postgres
class TestImportacao(ComBanco):

    def setUp(self):
        super().setUp()
        self.ppr = pg_ppr.PortaDoPpr(self.app, "geovani.pena")

    def test_importar_de_novo_nao_duplica(self):
        primeira = importar_ppr.importar(self.ppr, SEMENTE)
        segunda = importar_ppr.importar(self.ppr, SEMENTE)
        self.assertEqual(primeira["novas"], 5)   # 3 partes, 1 dado, condições
        self.assertEqual(segunda, {"novas": 0, "corrigidas": 0, "iguais": 5})
        self.assertEqual(self._conta(
            "SELECT count(*) FROM nucleo.ppr_parte"), 2)

    def test_texto_corrigido_substitui_o_vigente(self):
        importar_ppr.importar(self.ppr, SEMENTE)
        nova = copy.deepcopy(SEMENTE)
        nova["partes"]["identificacao"]["texto"] = "Rua Y"
        contas = importar_ppr.importar(self.ppr, nova)
        self.assertEqual(contas["corrigidas"], 1)
        partes = self.ppr.partes("ANA")
        self.assertEqual(partes["identificacao"].texto, "Rua Y")
        # O anterior continua lá; só deixou de ser o vigente.
        self.assertEqual(self._conta(
            "SELECT count(*) FROM nucleo.ppr_parte"
            " WHERE chave = 'identificacao'"), 2)

    def test_parte_sem_fonte_cita_o_documento(self):
        importar_ppr.importar(self.ppr, SEMENTE)
        self.assertEqual(self.ppr.partes("ANA")["anexo/estrutura"].fonte,
                         "fonte/PPR_DUO_JAN25.pdf")

    def test_simular_nao_grava(self):
        importar_ppr.importar(self.ppr, SEMENTE, simular=True)
        self.assertEqual(self._conta("SELECT count(*) FROM nucleo.log"), 0)

    def test_condicoes_vem_da_gq(self):
        importar_ppr.importar(self.ppr, SEMENTE)
        self.assertEqual(self.ppr.condicoes("ANA"), frozenset())
        self.assertIsNone(self.ppr.condicoes("CEL"))


@precisa_do_postgres
class TestDonoEClinica(ComBanco):

    def setUp(self):
        super().setUp()
        self.ppr = pg_ppr.PortaDoPpr(self.app, "geovani.pena")

    def test_modulo_nao_grava_na_tabela_de_outro(self):
        with self.assertRaises(GravacaoRecusada):
            pg_ppr.gravar(self.ppr._porta, modulo="qualidade",
                          tabela="seguranca.ppr_parte", quem="geovani.pena",
                          dados={"clinica": "CEL", "chave": "gq_riscos",
                                 "texto": "x", "fonte": "y"})

    def test_parte_de_uma_clinica_nao_vale_para_outra(self):
        importar_ppr.importar(self.ppr, SEMENTE)
        ident = ppr.CAPITULOS[0]
        self.assertTrue(self.ppr.fachadas("ANA")["fundacao"]("ANA", ident))
        self.assertFalse(self.ppr.fachadas("CEL")["fundacao"]("CEL", ident))
        # Fachada de uma leitura perguntada por outra clínica: não.
        self.assertFalse(self.ppr.fachadas("ANA")["fundacao"]("CEL", ident))

    def test_leitura_pela_tela(self):
        importar_ppr.importar(self.ppr, SEMENTE)
        leitura = pg_ppr.ler(self.app, "ANA")
        self.assertEqual(leitura.aviso, "")
        self.assertEqual(leitura.partes["gq_riscos"].modulo, "seguranca")
        self.assertEqual(len(ppr.planta(leitura.condicoes).capitulos), 22)


@precisa_do_postgres
class TestEdicaoNaTela(ComBanco):
    """O texto editado na aba PPR (pedido de 28/10/2026)."""

    def setUp(self):
        super().setUp()
        self.ppr = pg_ppr.PortaDoPpr(self.app, "geovani.pena")
        importar_ppr.importar(self.ppr, SEMENTE)

    def _editar(self, chave, texto, quem="geovani.pena"):
        anterior = self.ppr.partes("ANA").get(chave)
        modulo = anterior.modulo if anterior else "fundacao"
        pg_ppr.gravar_texto(pg_ppr.PortaDoPpr(self.app, quem), "ANA", modulo,
                            chave, texto, anterior)

    def test_edicao_substitui_e_guarda_documentos_e_origem(self):
        self._editar("anexo/estrutura", "Organograma de out/2026")
        vigente = self.ppr.partes("ANA")["anexo/estrutura"]
        self.assertEqual(vigente.texto, "Organograma de out/2026")
        self.assertEqual(vigente.documentos, [{"titulo": "Organograma"}])
        self.assertEqual(vigente.fonte,
                         "edição no ISOCENTRO sobre fonte/PPR_DUO_JAN25.pdf")
        self._editar("anexo/estrutura", "de novo")
        self.assertEqual(self.ppr.partes("ANA")["anexo/estrutura"].fonte,
                         "edição no ISOCENTRO sobre fonte/PPR_DUO_JAN25.pdf")

    def test_quem_editou_fica_no_log(self):
        self._editar("identificacao", "Rua Z", quem="fisico.teste")
        self.assertEqual(self._conta(
            "SELECT quem FROM nucleo.log ORDER BY posicao DESC LIMIT 1"),
            "fisico.teste")

    def test_duas_estacoes_editando_a_mesma_versao(self):
        """A segunda a salvar corrige uma versão que já não é a vigente: o
        banco recusa, e o texto da primeira não some em silêncio."""
        anterior = self.ppr.partes("ANA")["identificacao"]
        pg_ppr.gravar_texto(self.ppr, "ANA", "fundacao", "identificacao",
                            "da estação 1", anterior)
        with self.assertRaises(GravacaoRecusada):
            pg_ppr.gravar_texto(self.ppr, "ANA", "fundacao", "identificacao",
                                "da estação 2", anterior)
        self.assertEqual(self.ppr.partes("ANA")["identificacao"].texto,
                         "da estação 1")

    def test_parte_sem_dado_ganha_a_primeira_versao(self):
        self._editar("ioes", "Os IOEs são…")
        vigente = self.ppr.partes("ANA")["ioes"]
        self.assertEqual(vigente.fonte, "edição no ISOCENTRO")
        self.assertEqual(vigente.modulo, "fundacao")


if __name__ == "__main__":
    unittest.main()
