"""O shell Torre de controle: Início, doca, fila de ação e contraste (R-23).

O que estes testes guardam (DESIGN.md e EXPERIENCE.md da UX):

- zero, "normal" ou "Nada precisa de ação" aparecendo por FALTA de dado — a
  fila sem fonte mostrando 0 e o painel sem banco dizendo que está tudo em
  dia (State Patterns);
- módulo que o perfil não vê aparecendo na doca, ou a doca com contagem;
- "Todas" para quem não é físico;
- o programa abrindo dentro de um módulo, ou a tela trocando por trás do
  Início sem ninguém ver;
- texto ou sinal abaixo do contraste da UX (texto 4,5:1, sinal 3:1).
"""
from __future__ import annotations

import os
import re
import unittest
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel

    from isocentro.interface import estilo as st
    from isocentro.interface import torre
except ImportError:  # pragma: no cover
    torre = None

from tests.limpeza_de_tela import load_tests  # noqa: F401


def _app():
    return QApplication.instance() or QApplication([])


def _alerta(n, sev="alta", estado="aberto", vistos=()):
    return SimpleNamespace(severidade=sev, objeto=f"objeto {n}",
                           motivo="motivo", vence_em=None, clinica="ANA",
                           estado=estado, vistos=list(vistos),
                           quando=datetime(2026, 10, 28, 8, n))


@unittest.skipIf(torre is None, "PySide6 indisponível")
class TestRegrasPuras(unittest.TestCase):

    def test_doca_recortada_pelo_perfil(self):
        nomes = lambda p: [m.chave for m in torre.modulos_do_papel(p)]  # noqa: E731
        self.assertEqual(nomes("medico"), ["radioteraficha", "plano",
                                           "tratamento", "seguranca",
                                           "conhecimento"])
        self.assertNotIn("radioteraficha", nomes("spr"))
        self.assertEqual(len(nomes("admin")), 9)
        self.assertEqual(nomes(""), [])

    def test_todas_so_para_quem_ve_tudo(self):
        self.assertEqual(torre.clinicas_do_papel("tecnico"),
                         ["CEL", "BET", "DUO"])
        self.assertEqual(torre.clinicas_do_papel("fisico")[-1], torre.TODAS)

    def test_duo_e_ana_no_banco(self):
        """A tela diz DUO; o banco chama de ANA (``atividades_db.UNIDADES``)."""
        self.assertEqual(torre.codigos_da_escolha("DUO"), ["ANA"])
        self.assertEqual(torre.codigos_da_escolha(torre.TODAS),
                         ["CEL", "BET", "ANA"])
        self.assertEqual(torre.rotulo_da_clinica("ANA"), "DUO")


@unittest.skipIf(torre is None, "PySide6 indisponível")
class TestInicio(unittest.TestCase):

    def setUp(self):
        _app()

    def _inicio(self, papel="fisico", **kw):
        return torre.Inicio({"usuario": "u", "nome": "Geova", "papel": papel},
                            **kw)

    def test_fila_sem_fonte_nao_e_zero(self):
        ini = self._inicio()
        for coluna in ini.colunas:
            for nome, numero in coluna.contadores.items():
                with self.subTest(clinica=coluna.codigo, fila=nome):
                    self.assertNotEqual(numero.text(), "0")
                    self.assertEqual(numero.text(), "—")

    def test_todas_abre_tres_colunas_e_a_clinica_uma(self):
        ini = self._inicio()
        self.assertEqual([c.codigo for c in ini.colunas], ["CEL", "BET", "ANA"])
        ini.seletor.botoes["DUO"].click()
        self.assertEqual([c.codigo for c in ini.colunas], ["ANA"])

    def test_clinica_lembrada_vale_se_existe(self):
        self.assertEqual(self._inicio(clinica_inicial="BET").clinica(), "BET")
        # "Todas" lembrada de quando a pessoa era físico não vale para técnico.
        self.assertEqual(self._inicio("tecnico", clinica_inicial="Todas")
                         .clinica(), "CEL")

    def test_sem_banco_nao_diz_que_nada_precisa_de_acao(self):
        ini = self._inicio()
        ini.mostrar_alertas(None)
        self.assertEqual(ini.painel_acao.lbl_vazio.text(), torre.SEM_BANCO)
        ini.mostrar_alertas([])
        self.assertEqual(ini.painel_acao.lbl_vazio.text(), torre.NADA_A_FAZER)

    def test_cinco_linhas_e_ver_mais(self):
        ini = self._inicio()
        ini.mostrar_alertas([_alerta(i) for i in range(7)])
        self.assertEqual(len(ini.painel_acao.linhas), 5)
        self.assertEqual(ini.painel_acao.btn_ver_mais.text(), "ver mais 2")
        self.assertIn("7", ini.rot_zona2.text())
        ini.painel_acao.btn_ver_mais.click()
        self.assertEqual(len(ini.painel_acao.linhas), 7)

    def test_severidade_tem_forma_e_palavra(self):
        """A cor sozinha falha para deutan e protan (DESIGN.md, Daltonismo)."""
        ini = self._inicio()
        ini.mostrar_alertas([_alerta(1, "alta"), _alerta(2, "atencao"),
                             _alerta(3, "informativo")])
        chips = [l.findChildren(QLabel)[0].text() for l in ini.painel_acao.linhas]
        self.assertTrue(chips[0].startswith("▲") and "ALTA" in chips[0])
        self.assertTrue(chips[1].startswith("◆") and "ATENÇÃO" in chips[1])
        self.assertTrue(chips[2].startswith("○") and "INFO" in chips[2])

    def test_visto_diz_quem_e_quando(self):
        ini = self._inicio()
        ini.mostrar_alertas([_alerta(1, estado="visto",
                                     vistos=[("Bruno",
                                              datetime(2026, 10, 28, 7, 12))])])
        textos = [l.text() for l in ini.painel_acao.linhas[0].findChildren(QLabel)]
        self.assertIn("visto · Bruno · 07:12", textos)

    def test_doca_sem_contagem(self):
        ini = self._inicio("admin")
        self.assertEqual(len(ini.blocos), 9)
        for bloco in ini.blocos:
            for rotulo in bloco.findChildren(QLabel):
                with self.subTest(modulo=bloco.modulo.chave):
                    self.assertIsNone(re.search(r"\d", rotulo.text()))

    def test_abrir_fila_sem_destino_esta_apagado_e_diz_por_que(self):
        ini = self._inicio()
        self.assertFalse(ini.painel_acao.btn_abrir_fila.isEnabled())
        self.assertIn("R-19", ini.painel_acao.btn_abrir_fila.toolTip())


def _luminancia(cor: str) -> float:
    def canal(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    h = cor.lstrip("#")
    r, g, b = (canal(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@unittest.skipIf(torre is None, "PySide6 indisponível")
class TestContraste(unittest.TestCase):
    """Os pares da tabela de contrastes do DESIGN.md, nos dois modos, contra os
    valores que o ``estilo`` usa de verdade (WCAG 2.x)."""

    TEXTO = [("TEXTO", "FUNDO"), ("TEXTO", "SUPERFICIE"),
             ("TEXTO_SECUNDARIO", "FUNDO"),
             ("TEXTO_SECUNDARIO", "SUPERFICIE_ELEVADA"),
             ("ACAO", "FUNDO"), ("ACAO", "ACAO_FUNDO"), ("SOBRE_ACAO", "ACAO"),
             ("ALTA_TEXTO", "ALTA_FUNDO"), ("ATENCAO_TEXTO", "ATENCAO_FUNDO"),
             ("INFO_TEXTO", "INFO_FUNDO"), ("ESTADO_NEUTRO", "SUPERFICIE"),
             ("DADO_AO_VIVO", "SUPERFICIE"), ("DADO_ESPELHO", "SUPERFICIE")]
    SINAL = [("ALTA", "SUPERFICIE"), ("ATENCAO", "SUPERFICIE"),
             ("INFO", "SUPERFICIE"), ("FOCO", "SUPERFICIE")]

    def test_texto_e_sinal_acima_do_piso(self):
        for modo, paleta in st.MODOS.items():
            for pares, piso in ((self.TEXTO, 4.5), (self.SINAL, 3.0)):
                for frente, fundo in pares:
                    with self.subTest(modo=modo, par=f"{frente}/{fundo}"):
                        self.assertGreaterEqual(
                            round(_contraste(paleta[frente], paleta[fundo]), 2),
                            piso)


@unittest.skipIf(torre is None, "PySide6 indisponível")
class TestJanela(unittest.TestCase):

    def setUp(self):
        _app()
        from isocentro.interface import gui
        self.gui = gui
        self.j = gui.JanelaPrincipal({"usuario": "f", "papel": "fisico"})
        self.addCleanup(self.j.deleteLater)

    def test_abre_no_inicio(self):
        self.assertTrue(self.j._no_inicio())

    def test_bloco_em_construcao_abre_a_tela_que_diz_isso(self):
        self.j._abrir_modulo("plano")
        self.assertIs(self.j._conteudo_modulo.currentWidget(),
                      self.j.tela_em_construcao)
        self.assertIn("em construção", self.j.tela_em_construcao.lbl_frase.text())
        self.assertFalse(self.j._barra_modo.isVisibleTo(self.j.pag_modulo))

    def test_documentacao_abre_o_ppr_sem_dado_e_sem_emitir(self):
        """O PPR vivo sem nenhum módulo dono pronto: cada capítulo "sem dado"
        e o botão de emitir apagado, com o motivo — nunca um PPR "pronto"
        com capítulo vazio (spec Documentação CAP-10)."""
        from isocentro.dominio import ppr
        tela = self.j.documentacao
        # Sem banco: a estação de quem roda a suíte pode ter o
        # ISOCENTRO_PG_APP apontado para o banco de desenvolvimento.
        tela._ler = lambda _c: ppr.Leitura({}, None, {})
        self.j._abrir_modulo("documentacao")
        self.assertIs(self.j._conteudo_modulo.currentWidget(), tela)
        self.assertEqual(tela.tabela.rowCount(), len(ppr.situacoes("CEL")))
        for i in range(tela.tabela.rowCount()):
            self.assertIn("sem dado", tela.tabela.item(i, 3).text())
        self.assertFalse(tela.btn_emitir.isEnabled())
        self.assertTrue(tela.btn_emitir.toolTip())

    def test_documentacao_com_todas_abre_numa_unidade(self):
        """Cada PPR é de uma clínica: com "Todas" no Início a aba abria
        vazia, pedindo que se voltasse ao Início para escolher."""
        from isocentro.dominio import ppr
        tela = self.j.documentacao
        tela._ler = lambda _c: ppr.Leitura({}, None, {})
        tela.definir_clinica("", "Todas")
        self.assertEqual(tela.clinica(), "CEL")
        self.assertEqual(tela.cmb_clinica.currentText(), "CEL")

    def test_alt_home_volta_ao_inicio(self):
        self.j._abrir_modulo("radioteraficha")
        self.assertFalse(self.j._no_inicio())
        self.j._mostrar_inicio()
        self.assertTrue(self.j._no_inicio())

    def test_troca_por_codigo_leva_ao_modulo(self):
        """Soltar uma pasta na janela com o Início na frente carregava o caso
        por trás dele, sem ninguém ver."""
        from isocentro.interface import fichinha
        self.j._ir_para_modo(fichinha.MODO_CAPA)
        self.assertFalse(self.j._no_inicio())
        self.assertEqual(self.j._modulo_aberto, "radioteraficha")

    def test_barra_de_status_diz_quem_e_onde(self):
        self.assertEqual(self.j.lbl_identidade.text(), "f · físico · Todas")


if __name__ == "__main__":
    unittest.main()
