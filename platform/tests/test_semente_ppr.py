"""A semente do PPR vivo tirada do JSON do ppr-streamlit (CEL).

O que estes testes guardam:

- parte da planta faltando na semente: o importador não teria o que gravar e
  o PPR vivo nasceria com um capítulo a menos que o vigente;
- o caminho do anexo apontando para a máquina onde o JSON foi gravado
  (``G:/4 - FÍSICA/...``), que não existe aqui;
- a versão anterior de um certificado ("Barometro (2022).pdf") entrando como
  anexo ao lado da vigente;
- a pasta de ASOs copiada para a fonte: o ASO não entra no PPR vivo
  (Documentação CAP-3).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from isocentro.dominio import ppr
from tools import semente_ppr as sp

_JSON = {
    "instalacao": {"nome": "Clínica Fictícia", "matricula_cnen": "0", "grupo": "7",
                   "subgrupo": "7C", "objetivo": "Tratamento", "mes": "Maio",
                   "ano": "2026"},
    "textos_caps": {"controle_acesso": "Barreiras físicas.",
                    "gerencia_rejeitos": "Fonte devolvida ao fabricante."},
    "pdfs": {"sevrra": ["G:/4 - FÍSICA/X/anexos/PDFs/SEVRRA/SEVRRA_A.pdf"],
             "certificados_outros": []},
    "equipes_medicos": [{"nome": "Fulano Fictício"}],
    "testes_diarios_braqui": [{"teste": "x", "tolerancia": "1%"}],
}


class TestSementeCBR(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pasta = self.tmp / "CEL" / "ppr"
        (self.pasta / "fonte").mkdir(parents=True)
        self.json = self.pasta / "fonte" / "PPR_ficticio.json"
        self.json.write_text(json.dumps(_JSON), encoding="utf-8")
        origem = self.tmp / "PDFs"
        for rel in ("SEVRRA/SEVRRA_A.pdf", "Certificados de Calibração/Outros/Barometro.pdf",
                    "Certificados de Calibração/Outros/Barometro (2022).pdf",
                    "ASOS/ASOS.pdf"):
            (origem / rel).parent.mkdir(parents=True, exist_ok=True)
            (origem / rel).write_bytes(b"%PDF")
        sp.copiar_anexos_cel(origem, self.pasta)
        self.s = sp.semente_cel(self.json, self.pasta)

    def test_toda_parte_da_planta_esta_na_semente(self):
        for parte in ppr.planta().partes():
            chave = parte.chave if not isinstance(parte, ppr.Anexo) else f"anexo/{parte.chave}"
            if parte is ppr.SEVRRA:
                chave = f"anexo/{parte.chave}"
            with self.subTest(parte=chave):
                self.assertIn(chave, self.s["partes"])
                self.assertEqual(self.s["partes"][chave]["modulo"], parte.modulo)

    def test_caminho_do_json_vira_caminho_na_fonte(self):
        doc = self.s["partes"]["anexo/gq_sevrra"]["documentos"][0]
        self.assertEqual(doc["arquivo"], "fonte/anexos/SEVRRA/SEVRRA_A.pdf")
        self.assertNotIn("falta", doc)

    def test_certificado_pela_pasta_sem_a_versao_anterior(self):
        docs = self.s["partes"]["anexo/instrumentos"]["documentos"]
        self.assertEqual([d["titulo"] for d in docs], ["Barometro"])
        self.assertIn("não listado no JSON", docs[0]["fonte"])

    def test_asos_nao_sao_copiados(self):
        self.assertFalse((self.pasta / "fonte" / "anexos" / "ASOS").exists())

    def test_rejeitos_presente_com_braquiterapia(self):
        self.assertEqual(self.s["condicoes"], [ppr.FONTE_RADIOATIVA])
        self.assertIn("devolvida", self.s["partes"]["anexo/rejeitos"]["texto"])

    def test_resumo_nao_mostra_conteudo(self):
        """O resumo vai ao terminal: só contagem, nunca nome da equipe."""
        self.assertNotIn("Fulano", sp.resumo(self.s))
        self.assertNotIn("Fictícia", sp.resumo(self.s))


class TestLeituraDoPDF(unittest.TestCase):
    """Regras da leitura do PDF (BET e DUO), cada uma de um erro achado ao
    conferir as sementes contra os PPRs de jul/2026 e jan/2025."""

    def test_linha_so_com_a_primeira_celula(self):
        """"(modos de irradiação…)" fecha o teste de cima; "Detector" (BET,
        G.4) abre a linha de baixo."""
        regs = sp._registros([
            ["Teste", "Tolerância"],
            ["Verificação de travas", "Funcionando"],
            ["(modos de irradiação; filtro)", ""],
        ])
        self.assertEqual(regs, [{"teste": "Verificação de travas (modos de irradiação; filtro)",
                                 "tolerancia": "Funcionando"}])
        regs = sp._registros([
            ["Item", "Fabricante", "Modelo", "No. Série", "Data Fabricação", "Tipo"],
            ["Detector", "", "", "", "", ""],
            ["Planar para QA", "Sun Nuclear", "MapCheck", "1", "set./2009", "Diodo"],
        ])
        self.assertEqual(regs[0]["obj"], "Detector Planar para QA")

    def test_coluna_partida_cola_na_anterior(self):
        """"Data brica" | "Fa- ção" (DUO, F.1): a data saía partida."""
        regs = sp._registros([
            ["Fonte Selada", "Data brica", "Fa- ção", "Tipo"],
            ["Sr-90", "09/04", "/2019", "Beta"],
        ])
        self.assertEqual(regs[0]["data"], "09/04/2019")

    def test_cabecalho_por_palavra_inteira(self):
        """Por pedaço, "Carga Horária" virava RA e "CRTR" virava RT."""
        self.assertEqual(sp._campo("Carga Horária"), "carga")
        self.assertEqual(sp._campo("CRTR"), "crtr")
        self.assertEqual(sp._campo("RA"), "ra")
        self.assertEqual(sp._campo("Função"), "cargo")

    def test_quebra_na_celula(self):
        self.assertEqual(sp._celula("PC Electro-\nmeter"), "PC Electrometer")
        self.assertEqual(sp._celula("1014300MW-\n94167003"), "1014300MW-94167003")

    def test_cnpj_nao_perde_o_hifen(self):
        self.assertEqual(sp._texto(["nº 23.264.130/0001-", "37, encontra-se"]),
                         "nº 23.264.130/0001-37, encontra-se")

    def test_vide_sai_e_mencao_a_anexo_vira_marcador(self):
        p = ppr.planta(frozenset())
        self.assertEqual(sp._sem_vide("Vide anexo H e seção 18.", p), "")
        self.assertEqual(sp._sem_vide("Vide aenxo J.", p), "")
        self.assertEqual(sp._sem_vide("conforme o diagrama no anexo D.", p),
                         "conforme o diagrama no anexo {anexo:areas}.")

    def test_glifos_da_bet(self):
        self.assertEqual(sp._limpo("sob o nž 11"), "sob o nº 11")
        self.assertEqual(sp._limpo("classiﬁcada"), "classificada")

    def test_equipamento_e_tps_rotulados(self):
        itens = sp._itens_rotulados([
            "Bloco E.1 - Acelerador Linear de Teleterapia",
            "Fabricante: Varian Modelo: Clinac 600CD Nº de Série: 1196",
            "Taxa de dose nominal: 100-600 cGy/min",
        ])
        self.assertEqual(itens[0]["nome"], "Acelerador Linear de Teleterapia")
        self.assertEqual(itens[0]["serie"], "1196")
        tps = sp._itens_rotulados([
            "Bloco J.1 - Sistema 1 Nome Comercial: Eclipse",
            "Fabricante: Varian Versão: 15.6 Ténicas Implementadas: 3D CRT",
        ])
        self.assertEqual((tps[0]["nome"], tps[0]["versao"], tps[0]["tecnicas"]),
                         ("Eclipse", "15.6", "3D CRT"))

    def test_instalacao_do_texto_do_corpo(self):
        inst = sp._instalacao(
            "O CTR Fictício LTDA (Número de matrícula CNEN 15.934) inscrita no "
            "C.N.P.J. sob o nº 00.000.000/0001-91, encontra-se situado à Rua A, "
            "CEP 74215-170, telefone para contato: (62) 3933-0200.\n\nO Horário "
            "de tratamento de pacientes é das 07:00h às 19:00h.",
            "A citada instituição tem por objetivo o Tratamento.",
            "classificada com do GRUPO 7, SUBGRUPO 7C.")
        self.assertEqual(inst["cnpj"], "00.000.000/0001-91")
        self.assertEqual(inst["horario"], "07:00h às 19:00h")
        self.assertEqual((inst["grupo"], inst["subgrupo"]), ("7", "7C"))


if __name__ == "__main__":
    unittest.main()
