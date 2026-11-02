"""A planta do PPR vivo (spec Documentação CAP-10).

O que estes testes guardam, cada um tirado dos três PPRs vigentes:

- número de capítulo e letra de anexo fixos: na DUO (sem fonte radioativa)
  o capítulo de rejeitos não existe, e o "Vide anexo K" do capítulo 13 aponta
  para Sistemas de Planejamento — com letra fixa apontaria para Técnicas;
- parte aparecendo "com dado" sem que o módulo dono a tenha dado, ou um
  capítulo "com dado" com o anexo dele vazio;
- o botão de emitir aceso com parte faltando ou com "Todas".
"""
from __future__ import annotations

import unittest

from isocentro.dominio import ppr


def _todos(_clinica, _parte):
    return True


TODAS_AS_FACHADAS = {m: _todos for m in ppr.MODULOS}


class TestPlanta(unittest.TestCase):

    def test_com_fonte_radioativa_23_capitulos_e_anexos_ate_r(self):
        """CEL, mai/2026 (``PPR.tex``)."""
        p = ppr.planta()
        self.assertEqual(len(p.capitulos), 23)
        self.assertEqual(p.anexos[-1][0], "R")
        self.assertEqual(dict((c.chave, n) for n, c in p.capitulos)["rejeitos"], "18")

    def test_sem_fonte_radioativa_22_capitulos_e_anexos_ate_q(self):
        """DUO, jan/2025: sumário p. 6–7."""
        p = ppr.planta(frozenset())
        self.assertEqual(len(p.capitulos), 22)
        self.assertEqual(p.anexos[-1][0], "Q")
        numeros = dict((c.chave, n) for n, c in p.capitulos)
        self.assertEqual(numeros["aso"], "18")
        self.assertEqual(numeros["emergencia"], "22")

    def test_letras_dos_anexos_como_no_ppr_da_duo(self):
        """DUO p. 11–15: monitores "Vide anexo I", TPS "J", técnicas "K",
        ASO "N", emergência "Q"."""
        p = ppr.planta(frozenset())
        for chave, letra in (("estrutura", "A"), ("responsabilidades", "C"),
                             ("gq", "H"), ("monitores", "I"), ("tps", "J"),
                             ("tecnicas", "K"), ("aso", "N"),
                             ("emergencia", "Q")):
            with self.subTest(chave=chave):
                self.assertEqual(p.letra(chave), letra)

    def test_letras_dos_anexos_como_no_ppr_da_cel(self):
        """``ppr_pdf``: rejeitos "J", TPS "K", ASO "O", emergência "R"."""
        p = ppr.planta()
        for chave, letra in (("rejeitos", "J"), ("tps", "K"), ("aso", "O"),
                             ("emergencia", "R")):
            with self.subTest(chave=chave):
                self.assertEqual(p.letra(chave), letra)

    def test_todo_anexo_citado_existe_e_todo_dono_e_conhecido(self):
        chaves = {a.chave for a in ppr.ANEXOS}
        for cap in ppr.CAPITULOS:
            with self.subTest(cap=cap.chave):
                self.assertIn(cap.modulo, ppr.MODULOS)
                if cap.anexo:
                    self.assertIn(cap.anexo, chaves)

    def test_donos_decididos_em_28_10(self):
        """GQ: equipamentos e programa de GQ (era a falta de MLC e imagem);
        Segurança: análise de riscos (SEVRRA) dentro do capítulo da GQ;
        Fundação: grupo e subgrupo da NN-6.02."""
        caps = {c.chave: c for c in ppr.CAPITULOS}
        self.assertEqual(caps["equipamentos"].modulo, "qualidade")
        self.assertEqual(caps["gq"].modulo, "qualidade")
        riscos = {s.chave: s for s in caps["gq"].subsecoes}["gq_riscos"]
        self.assertEqual(riscos.modulo, "seguranca")
        self.assertEqual(caps["classificacao"].modulo, "fundacao")


class TestSituacao(unittest.TestCase):

    def test_sem_fachada_tudo_sem_dado(self):
        linhas = ppr.situacoes("CEL")
        self.assertEqual({s for _r, _p, s in linhas}, {ppr.SEM_DADO})

    def test_uma_linha_por_capitulo_e_o_anexo_c(self):
        linhas = ppr.situacoes("CEL")
        self.assertEqual(len(linhas), 24)
        self.assertEqual(linhas[-1][0], "Anexo C")

    def test_capitulo_da_gq_espera_o_sevrra_da_seguranca(self):
        """Com a GQ inteira e a Segurança vazia, o capítulo 12 continua sem
        dado: o 12.3 e o SEVRRA do anexo H são dela."""
        linhas = ppr.situacoes("CEL", {"qualidade": _todos})
        gq = next(s for _r, p, s in linhas if p.chave == "gq")
        equip = next(s for _r, p, s in linhas if p.chave == "equipamentos")
        self.assertEqual(gq, ppr.SEM_DADO)
        self.assertEqual(equip, ppr.COM_DADO)

    def test_capitulo_com_anexo_de_outro_dono_espera_os_dois(self):
        """Corpo e anexo do mesmo capítulo podem ser de módulos diferentes
        no futuro; hoje não são, mas a regra é a do conjunto."""
        so_corpo = {"fundacao": lambda _c, parte: isinstance(parte, ppr.Capitulo)}
        linhas = ppr.situacoes("CEL", so_corpo)
        estrutura = next(s for _r, p, s in linhas if p.chave == "estrutura")
        identificacao = next(s for _r, p, s in linhas if p.chave == "identificacao")
        self.assertEqual(estrutura, ppr.SEM_DADO)
        self.assertEqual(identificacao, ppr.COM_DADO)

    def test_fachada_recebe_a_clinica(self):
        """Parte de uma clínica não pode valer para outra."""
        linhas = ppr.situacoes("BET", {"plano": lambda cl, _p: cl == "CEL"})
        self.assertEqual({s for _r, _p, s in linhas}, {ppr.SEM_DADO})


class TestEmitir(unittest.TestCase):

    def test_parte_faltando_impede_e_diz_quantas(self):
        motivo = ppr.motivo_para_nao_emitir("CEL", ppr.situacoes("CEL"))
        self.assertIn("Faltam 24 parte", motivo)

    def test_todas_impede_mesmo_com_tudo_com_dado(self):
        linhas = ppr.situacoes("", TODAS_AS_FACHADAS)
        self.assertIn("por clínica", ppr.motivo_para_nao_emitir("", linhas))

    def test_tudo_com_dado_libera(self):
        linhas = ppr.situacoes("CEL", TODAS_AS_FACHADAS)
        self.assertEqual(ppr.motivo_para_nao_emitir("CEL", linhas), "")


if __name__ == "__main__":
    unittest.main()
