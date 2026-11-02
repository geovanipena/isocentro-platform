"""A aba PPR lendo as partes gravadas (R-85, etapa 2).

O que estes testes guardam:

- o texto do PPR existindo no banco e a aba sem mostrá-lo (o pedido de
  28/10/2026: "os textos ainda não aparecem");
- parte não gravada aparecendo em branco, como se o PPR vigente não tivesse
  nada ali, em vez de "sem dado — <módulo>";
- capítulo e anexo de mesma chave (``estrutura``) trocando de texto;
- "Vide anexo" com a letra de outra planta (a DUO não tem rejeitos);
- o botão de emitir aceso com tudo "com dado", sem gerador para emitir;
- o motivo de não ter lido o banco escondido.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ISOCENTRO_USERS_DIR", tempfile.mkdtemp())

from isocentro.dominio import ppr  # noqa: E402

try:
    from PySide6.QtWidgets import QApplication
    _APP = QApplication.instance() or QApplication([])
    from isocentro.interface import documentacao_tela  # noqa: E402
    _MOTIVO = ""
except Exception as exc:  # noqa: BLE001
    documentacao_tela = None
    _MOTIVO = str(exc)

from tests.limpeza_de_tela import load_tests  # noqa: E402,F401


class _Gravada:
    def __init__(self, texto="", documentos=(), fonte="PPR.pdf, p. 1"):
        self.texto = texto
        self.documentos = list(documentos)
        self.fonte = fonte


def _leitura_completa(condicoes=frozenset()):
    """Toda parte da planta gravada, com o texto dizendo de quem é."""
    p = ppr.planta(condicoes)
    partes = {ppr.chave_gravada(x): _Gravada(f"texto de {ppr.chave_gravada(x)}")
              for x in p.partes()}
    fachadas = {m: (lambda _c, x: ppr.chave_gravada(x) in partes)
                for m in ppr.MODULOS}
    return ppr.Leitura(partes, condicoes, fachadas)


class TestChaves(unittest.TestCase):

    def test_capitulo_e_anexo_de_mesma_chave_nao_se_confundem(self):
        cap = next(c for c in ppr.CAPITULOS if c.chave == "estrutura")
        anx = next(a for a in ppr.ANEXOS if a.chave == "estrutura")
        self.assertEqual(ppr.chave_gravada(cap), "estrutura")
        self.assertEqual(ppr.chave_gravada(anx), "anexo/estrutura")
        self.assertEqual(ppr.chave_gravada(ppr.SEVRRA), "anexo/gq_sevrra")

    def test_mencao_ao_anexo_usa_a_letra_da_planta_da_clinica(self):
        """DUO (sem fonte): TPS é J; CEL: K."""
        texto = "vide anexo {anexo:tps}"
        self.assertEqual(ppr.resolver_mencoes(texto, ppr.planta(frozenset())),
                         "vide anexo J")
        self.assertEqual(ppr.resolver_mencoes(texto, ppr.planta()),
                         "vide anexo K")

    def test_mencao_a_anexo_inexistente_aparece(self):
        self.assertEqual(
            ppr.resolver_mencoes("anexo {anexo:rejeitos}",
                                 ppr.planta(frozenset())), "anexo ?")


@unittest.skipIf(documentacao_tela is None, f"Qt indisponível: {_MOTIVO}")
class TestPainel(unittest.TestCase):

    def _painel(self, leitura, papel="fisico", gravador=None):
        painel = documentacao_tela.PainelDocumentacao(
            leitor=lambda _c: leitura, gravador=gravador,
            usuario={"usuario": "geovani.pena", "papel": papel})
        painel.definir_clinica("ANA", "DUO")
        return painel

    def _linha(self, painel, chave):
        return next(i for i, (_n, p, _s) in enumerate(painel._linhas)
                    if p.chave == chave)

    def _abrir(self, painel, chave, parte=None):
        painel.tabela.setCurrentCell(self._linha(painel, chave), 1)
        if parte:
            painel.seletor_partes.botoes[parte].click()

    def test_cada_parte_da_linha_tem_o_seu_botao(self):
        """Uma caixa com corpo e anexo juntos não tinha como saber o que
        salvar em cada registro."""
        painel = self._painel(_leitura_completa())
        self._abrir(painel, "estrutura")
        self.assertEqual(list(painel.seletor_partes.botoes),
                         ["Capítulo 3", "Anexo A"])
        self.assertEqual(painel.lbl_parte.text(), "3 Estrutura Organizacional")
        self.assertEqual(painel.texto.toPlainText(), "texto de estrutura")
        painel.seletor_partes.botoes["Anexo A"].click()
        self.assertEqual(painel.texto.toPlainText(), "texto de anexo/estrutura")

    def test_capitulo_da_gq_traz_subsecoes_e_sevrra(self):
        painel = self._painel(_leitura_completa())
        self._abrir(painel, "gq")
        self.assertEqual(list(painel.seletor_partes.botoes),
                         ["Capítulo 12", "12.1", "12.2", "12.3", "Anexo H",
                          "SEVRRA"])

    def test_parte_nao_gravada_diz_sem_dado_e_o_dono(self):
        leitura = _leitura_completa()
        del leitura.partes["anexo/estrutura"]
        painel = self._painel(leitura, papel="dosimetrista")
        self._abrir(painel, "estrutura", "Anexo A")
        self.assertEqual(painel.texto.placeholderText(), "sem dado — Fundação")

    def test_vazio_documentos_e_fonte(self):
        leitura = _leitura_completa()
        leitura.partes["barreiras"] = _Gravada("", fonte="PPR_DUO.pdf, p. 13")
        leitura.partes["anexo/barreiras"] = _Gravada(
            "consta no anexo {anexo:barreiras}",
            [{"titulo": "Blindagem", "paginas": "40-52"}])
        painel = self._painel(leitura, papel="dosimetrista")
        self._abrir(painel, "barreiras")
        self.assertEqual(painel.texto.placeholderText(),
                         "(sem texto corrido no PPR vigente)")
        self.assertEqual(painel.lbl_origem.text(), "Fonte: PPR_DUO.pdf, p. 13")
        painel.seletor_partes.botoes["Anexo L"].click()
        self.assertEqual(painel.texto.toPlainText(), "consta no anexo L")
        self.assertIn("Documentos: Blindagem (p. 40-52)",
                      painel.lbl_origem.text())

    def test_na_edicao_a_mencao_fica_como_marcador(self):
        """Com a letra escrita, o texto salvo apontaria o anexo errado na
        clínica sem rejeitos."""
        leitura = _leitura_completa()
        leitura.partes["anexo/barreiras"] = _Gravada("vide {anexo:barreiras}")
        painel = self._painel(leitura)
        self._abrir(painel, "barreiras", "Anexo L")
        self.assertEqual(painel.texto.toPlainText(), "vide {anexo:barreiras}")

    def test_quem_nao_edita_le_so(self):
        painel = self._painel(_leitura_completa(), papel="dosimetrista")
        self._abrir(painel, "estrutura")
        self.assertTrue(painel.texto.isReadOnly())
        self.assertFalse(painel.btn_salvar.isEnabled())

    def test_salvar_grava_pelo_dono_e_reabre_a_mesma_parte(self):
        gravados = []
        leitura = _leitura_completa()
        painel = self._painel(
            leitura, gravador=lambda *a: gravados.append(a))
        self._abrir(painel, "gq", "12.3")
        self.assertFalse(painel.btn_salvar.isEnabled(), "nada alterado")
        painel.texto.setPlainText("SEVRRA revisado")
        self.assertTrue(painel.btn_salvar.isEnabled())
        painel.btn_salvar.click()
        quem, clinica, modulo, chave, texto, anterior = gravados[0]
        self.assertEqual((quem, clinica, modulo, chave, texto),
                         ("geovani.pena", "ANA", "seguranca", "gq_riscos",
                          "SEVRRA revisado"))
        self.assertIs(anterior, leitura.partes["gq_riscos"])
        self.assertEqual(painel.lbl_parte.text(),
                         "12.3 Planejamento de Análise de Riscos")

    def test_falha_ao_salvar_mantem_o_texto(self):
        def falha(*_a):
            raise RuntimeError("banco fora")
        painel = self._painel(_leitura_completa(), gravador=falha)
        self._abrir(painel, "estrutura")
        painel.texto.setPlainText("novo")
        with mock.patch.object(documentacao_tela.ui, "falhar") as falhar:
            painel.btn_salvar.click()
        falhar.assert_called_once()
        self.assertEqual(painel.texto.toPlainText(), "novo")
        self.assertTrue(painel.editado())

    def test_trocar_de_linha_com_edicao_pergunta(self):
        painel = self._painel(_leitura_completa())
        self._abrir(painel, "estrutura")
        painel.texto.setPlainText("novo")
        with mock.patch.object(documentacao_tela.ui, "confirmar",
                               return_value=False) as conf:
            painel.tabela.setCurrentCell(self._linha(painel, "ioes"), 1)
        conf.assert_called_once()
        self.assertEqual(painel.texto.toPlainText(), "novo")
        self.assertEqual(painel.tabela.currentRow(),
                         self._linha(painel, "estrutura"))
        with mock.patch.object(documentacao_tela.ui, "confirmar",
                               return_value=True):
            painel.tabela.setCurrentCell(self._linha(painel, "ioes"), 1)
        self.assertEqual(painel.texto.toPlainText(), "texto de ioes")

    def test_trocar_de_clinica_com_edicao_recusada_fica(self):
        painel = self._painel(_leitura_completa())
        self._abrir(painel, "estrutura")
        painel.texto.setPlainText("novo")
        with mock.patch.object(documentacao_tela.ui, "confirmar",
                               return_value=False):
            painel.cmb_clinica.setCurrentIndex(0)
        self.assertEqual(painel.clinica(), "ANA")
        self.assertEqual(painel.texto.toPlainText(), "novo")

    def test_tudo_com_dado_e_emitir_continua_apagado(self):
        painel = self._painel(_leitura_completa())
        situacoes = {painel.tabela.item(i, 3).text()
                     for i in range(painel.tabela.rowCount())}
        self.assertEqual(situacoes, {"com dado"})
        self.assertFalse(painel.btn_emitir.isEnabled())
        self.assertIn("gerador", painel.btn_emitir.toolTip())

    def test_condicoes_da_clinica_tiram_rejeitos(self):
        painel = self._painel(_leitura_completa())
        self.assertEqual(len(painel._planta.capitulos), 22)

    def test_aviso_do_banco_aparece_na_tela(self):
        painel = self._painel(ppr.Leitura({}, None, {}, "Banco central fora"))
        self.assertEqual(painel.lbl_aviso.text(), "Banco central fora")
        self.assertTrue(painel.faixa_aviso.isVisibleTo(painel))

    def test_seletor_da_aba_le_a_outra_unidade(self):
        """O pedido de 28/10/2026: cada PPR é de uma clínica, e a aba
        precisa trocar de unidade sem voltar ao Início."""
        lidas = []

        def leitor(clinica):
            lidas.append(clinica)
            return _leitura_completa(frozenset() if clinica != "CEL"
                                     else frozenset({ppr.FONTE_RADIOATIVA}))
        painel = documentacao_tela.PainelDocumentacao(leitor=leitor)
        painel.definir_clinica("ANA", "DUO")
        self.assertEqual(painel.cmb_clinica.currentText(), "DUO")
        painel.cmb_clinica.setCurrentIndex(0)
        self.assertEqual(painel.clinica(), "CEL")
        self.assertEqual(lidas, ["ANA", "CEL"])
        self.assertEqual(len(painel._planta.capitulos), 23)

    def test_abrir_na_mesma_unidade_le_uma_vez_so(self):
        lidas = []
        painel = documentacao_tela.PainelDocumentacao(
            leitor=lambda c: lidas.append(c) or _leitura_completa())
        self.assertEqual(lidas, [], "a tela não lê o banco ao nascer")
        painel.definir_clinica("CEL", "CEL")
        painel.definir_clinica("ANA", "DUO")
        self.assertEqual(lidas, ["CEL", "ANA"])

    def test_trocar_de_clinica_limpa_o_texto(self):
        painel = self._painel(_leitura_completa())
        painel.tabela.setCurrentCell(0, 1)
        self.assertTrue(painel.texto.toPlainText())
        painel.definir_clinica("", "Todas")
        self.assertEqual(painel.texto.toPlainText(), "")


if __name__ == "__main__":
    unittest.main()
