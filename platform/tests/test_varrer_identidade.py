"""A varredura de identificador de paciente no diff (``tools/varrer_identidade.py``).

Ela existe porque o custo do erro já foi medido: em 31/08/2026 havia 13
registros reais em 22 arquivos, e tirá-los custou fechar o repositório e
reescrever o histórico do git. Uma varredura só cumpre esse papel se acertar
nas duas direções, e os dois modos de errar têm preço diferente:

- **deixar passar** custa um vazamento que não se desfaz — daí a verificação da
  palavra isolada, que é a única que pega o nome partido por fim de linha (foi
  o que a primeira varredura de 31/08 perdeu em sete lugares);
- **acusar à toa** custa a confiança na ferramenta, e ferramenta em que não se
  confia se aprende a pular. Por isso a palavra que também está no pseudônimo
  não conta: "Helena" dentro de um nome inventado é a solução, não o problema.

Nota para quem editar este arquivo: **nenhum registro de 7 dígitos aparece
inteiro aqui**, os testes montam a string em pedaços. Escrito por extenso, este
arquivo acenderia a própria varredura que ele testa — e o commit que o traz
seria abortado por ele mesmo.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
    sys.path.insert(0, str(RAIZ / "tools"))

import varrer_identidade as vi  # noqa: E402

# Montado em pedaços de propósito — ver a nota do topo. E o número é INVENTADO:
# em 10/09/2026 este arquivo nasceu com um registro de verdade, copiado do
# `.identidades.json` na hora de escrever a fixture. Marcador de teste não se
# colhe do mapa; o mapa é justamente o que não pode circular.
REAL = "123" + "4567"
SINTETICO = "900" + "0001"

MAPA = {
    "registros": {REAL: SINTETICO},
    "nomes": {"Sícrano, Tadeu": "Amostro, Helena"},
}


def _diff(*linhas: str, arquivo: str = "isocentro/dominio/nomes.py") -> str:
    """Um diff mínimo, com o cabeçalho que a leitura de linha precisa."""
    corpo = "\n".join(linhas)
    return f"--- a/{arquivo}\n+++ b/{arquivo}\n@@ -10,0 +10,{len(linhas)} @@\n{corpo}\n"


class RegistroColadoAoCBR(unittest.TestCase):
    """A verificação que roda mesmo sem o `.identidades.json`.

    É a única que vale em estação nova, e por isso não pode depender de lista:
    sete dígitos ao lado de um `CEL`, com prefixo diferente de `900`, é
    registro de verdade em qualquer acervo.
    """

    def test_acha_as_grafias_do_acervo(self):
        """As seis grafias existem porque o acervo usa as seis.

        Uma busca só por `NNNNNNNCBR` perdeu `capa_dados.py` e
        `test_simulacao.py` em 31/08 — que existem justamente para provar que a
        busca aceita qualquer grafia.
        """
        for grafia in (f"{REAL}CEL", f"{REAL}-CEL", f"{REAL}-cel",
                       f"{REAL} CEL", f"{REAL} cel"):
            with self.subTest(grafia=grafia):
                achados = vi.varrer(_diff(f'+    paciente = "{grafia}"'), None)
                self.assertEqual(len(achados), 1)
                self.assertEqual(achados[0].tipo, "registro")

    def test_pseudonimo_nao_acende(self):
        """`900NNNN` é o número sintético — acusá-lo é acusar a correção."""
        self.assertEqual(vi.varrer(_diff(f'+  reg = "{SINTETICO}CEL"'), MAPA), [])

    def test_oito_digitos_nao_entram_pelos_sete_ultimos(self):
        """Sem o `(?<!\\d)`, um número de 8 dígitos vira registro pelos 7 finais."""
        self.assertEqual(vi.varrer(_diff(f'+  codigo = "1{REAL}CEL"'), None), [])

    def test_linha_removida_nao_acende(self):
        """Tirar dado sensível é o conserto; acusar o conserto trava a correção."""
        self.assertEqual(vi.varrer(_diff(f'-    reg = "{REAL}CEL"'), MAPA), [])


class ValoresDoMapa(unittest.TestCase):
    """O que só o `.identidades.json` sabe — e que some numa estação sem ele."""

    def test_numero_puro_sem_cel(self):
        """A grafia que não aparece numa busca por `[0-9]+CEL`.

        É por isso que o mapa é consultado além do padrão: o número solto só é
        reconhecível contra a lista dos que existem de verdade.
        """
        achados = vi.varrer(_diff(f"+    if registro == {REAL}:"), MAPA)
        self.assertEqual([a.tipo for a in achados], ["registro"])

    def test_sem_mapa_o_numero_puro_passa(self):
        """E é isso que a saída tem de anunciar: varredura parcial é parcial."""
        self.assertEqual(vi.varrer(_diff(f"+    if registro == {REAL}:"), None), [])

    def test_nome_inteiro(self):
        achados = vi.varrer(_diff('+    NOME = "Sícrano, Tadeu"'), MAPA)
        self.assertEqual([a.tipo for a in achados], ["nome"])

    def test_nome_sem_acento_e_em_caixa_alta(self):
        """O banco devolve em caixa alta e sem acento; o cadastro à mão, não.

        Comparar literalmente perderia metade das ocorrências do mesmo nome.
        """
        achados = vi.varrer(_diff('+    nome = "SÍCRANO, TADEU"'), MAPA)
        self.assertEqual([a.tipo for a in achados], ["nome"])

    def test_palavra_isolada_pega_o_nome_partido(self):
        """As sete sobras de 31/08: o mapa trocou a primeira metade do nome e a
        segunda estava na LINHA SEGUINTE, fora do alcance da busca pelo inteiro.
        """
        achados = vi.varrer(_diff('+    "Amostro, ",', '+    "Tadeu",'), MAPA)
        self.assertEqual([a.tipo for a in achados], ["nome (palavra)"])
        self.assertEqual(achados[0].linha, 11)

    def test_palavra_que_tambem_esta_no_pseudonimo_nao_conta(self):
        """"Helena" é do nome inventado. Acusá-lo é acusar a solução, e
        relatório que grita à toa é relatório que se aprende a pular."""
        self.assertEqual(vi.varrer(_diff('+    nome = "Amostro, Helena"'), MAPA), [])

    def test_palavra_comum_demais_nao_conta(self):
        """"Maria" veio de nome real e ainda assim não distingue ninguém.

        Ela acendia em `Retratamento, Maria`, o marcador inventado da fixture de
        retratamento — e um achado falso por rodada é o que faz a varredura
        virar aquela saída que se pula sem ler.
        """
        mapa = {"registros": {}, "nomes": {"TEREZA DE ANDRADE": "AMOSTRA DE SICRANA"}}
        self.assertEqual(vi.varrer(_diff('+  p = "Retratamento, Maria"'), mapa), [])
        # E o resto do nome continua acendendo: a exceção é de UMA palavra.
        achados = vi.varrer(_diff('+  p = "Andrade"'), mapa)
        self.assertEqual([a.tipo for a in achados], ["nome (palavra)"])

    def test_palavra_curta_nao_conta(self):
        """"de", "dos", "Sá" não distinguem ninguém e acenderiam em tudo."""
        mapa = {"registros": {}, "nomes": {"Sá, Ana": "Amostra, Bia"}}
        self.assertEqual(vi.varrer(_diff("+    texto = 'sa ana de casa'"), mapa), [])


class ArquivoNovoAindaForaDoGit(unittest.TestCase):
    """O buraco por onde este próprio arquivo entrou com dado real.

    Em 10/09/2026 o `tests/test_varrer_identidade.py` nasceu com um registro e um
    nome copiados do `.identidades.json` para servir de fixture, e o `--arvore`
    disse "nada de paciente real": `git diff` não enxerga arquivo não rastreado.
    Arquivo NOVO é onde o dado colado à mão aparece primeiro.
    """

    def test_arquivo_novo_vira_diff_de_adicao(self):
        import tempfile
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "novo.py").write_text(
                'NOME = "Sícrano, Tadeu"\n', encoding="utf-8")
            diff = vi.diff_dos_nao_rastreados(["novo.py"], raiz)
            achados = vi.varrer(diff, MAPA)
        self.assertEqual([a.tipo for a in achados], ["nome"])
        self.assertEqual((achados[0].arquivo, achados[0].linha), ("novo.py", 1))

    def test_arquivo_que_sumiu_nao_derruba(self):
        """A lista vem do `git status`; entre ele e a leitura o arquivo pode ir
        embora, e varredura que estoura no meio não confere nada."""
        self.assertEqual(vi.diff_dos_nao_rastreados(["nao_existe.py"]), "")


class OQueSaiNoRelatorio(unittest.TestCase):
    """A saída da varredura vira transcript, e transcript viaja."""

    def test_amostra_vem_mascarada(self):
        """Imprimir o registro inteiro vazaria o dado no relatório que o caça.

        O `arquivo:linha` é o que leva ao dado; a amostra serve só para saber se
        é registro ou nome.
        """
        achados = vi.varrer(_diff(f'+  reg = "{REAL}CEL"'), MAPA)
        self.assertNotIn(REAL, achados[0].amostra)
        self.assertTrue(achados[0].amostra.startswith(REAL[:2]))
        self.assertEqual(len(achados[0].amostra), len(REAL))

    def test_linha_e_arquivo_do_achado(self):
        """Achado sem linha manda procurar dado sensível de olho, no arquivo todo."""
        diff = _diff("+    a = 1", f'+    reg = "{REAL}CEL"', arquivo="tools/x.py")
        achados = vi.varrer(diff, MAPA)
        self.assertEqual((achados[0].arquivo, achados[0].linha), ("tools/x.py", 11))

    def test_mapa_ausente_nao_e_erro(self):
        """O `.identidades.json` está fora do git de propósito: numa estação
        nova ele não existe, e a ferramenta tem de rodar assim mesmo."""
        self.assertIsNone(vi.carregar_mapa(RAIZ / "nao_existe.json"))


if __name__ == "__main__":
    unittest.main()
