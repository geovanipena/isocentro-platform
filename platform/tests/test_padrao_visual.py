"""A trava do padrão de tela — o que impede a divergência de NASCER.

``test_padrao_ui.py`` guarda o padrão nos diálogos que ele **lista**: monta cada
um, olha o rodapé e confere a ordem dos botões. É o que garante que os
convertidos continuam certos.

O que faltava é o outro lado: uma tela NOVA, montada com ``QDialog`` cru e
``QTabWidget`` cru, não é pega por ninguém — nasce fora do padrão e só se
descobre por print de tela, uma tela de cada vez, depois de pronta. Foi assim
que a Administração e o Formulário ficaram meses com a barra de abas do sistema
ao lado das abas estilizadas do Posicionamento, na mesma janela.

O desvio nunca veio de discordância: veio de esquecimento. Quem monta uma tela
escreve ``QTabWidget()`` porque é o que o Qt oferece, e a linha do
``estilizar_abas`` não aparece sozinha. Estes testes leem o CÓDIGO-FONTE e
reprovam o esquecimento no lugar onde ele custa segundos, e não semanas.

**Como sair do padrão, quando é preciso:** acrescentar o caso a ``EXCECOES``
com o motivo escrito. Exceção com nome e motivo é decisão registrada; exceção
silenciosa é a divergência de volta.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path
from tests import fontes

RAIZ = Path(__file__).resolve().parent.parent

# Onde o padrão é DEFINIDO — aqui o Qt cru é a matéria-prima, não o desvio.
FONTES_DO_PADRAO = {"ui.py", "estilo.py", "aparencia.py"}

# Fugas do padrão que são decisão, não esquecimento. Chave: ``arquivo:nome``.
EXCECOES = {
    # Era ``tratamento.py:_JanelaImagem`` até a R-13 (13/10/2026) levar a
    # peça para o ``tratamento_pecas.py``: o teste lê o TEXTO do arquivo, e a
    # reimportação não o satisfaz.
    "tratamento_pecas.py:_JanelaImagem":
        "A lupa da imagem: sem rodapé e sem margem, de propósito — existe para "
        "UMA coisa (ver o corte de perto) e fecha no próprio clique. O rodapé "
        "do ui.Dialogo acrescentaria um botão a uma janela que não faz "
        "pergunta nenhuma.",
}

# Arquivos onde ``#rrggbb`` não é desvio: a paleta da tela não vale ali.
HEX_PERMITIDO = {
    "ficha_pdf.py": "cores do PAPEL (reportlab) — a ficha impressa não tem modo noite",
    "capa_pdf.py": "cores do PAPEL — idem",
    "rodape.py": "cor do PAPEL — idem",
    "grafico_dvh.py": "paleta do gráfico: cada estrutura tem a sua cor, igual nos dois modos",
    "diff_versoes.py": "HTML do comparador de versões, montado fora do Qt",
    "agendamento_tela.py": "cores de PLANO: o mesmo plano tem de sair da mesma "
                           "cor nos dois modos, e o quase-preto que vai por cima",
    "visualizador.py": "o preto do corte, que casa com a máscara da imagem",
    "edicao_ficha.py": "a tarja amarela da ficha, reproduzida na tela",
    "agenda_tela.py": "o ponto por sítio: as cores REAIS do ARIA (ditadas "
                      "pelo usuário em 24/09/2026), não a paleta do tema — "
                      "igual nos dois modos, mesmo critério do dvh.py",
}

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _modulos():
    """Os ``.py`` do pacote — o programa. ``tools/`` e ``tests/`` ficam de fora:
    são bancada, não tela de sala.

    Era ``RAIZ.glob("*.py")``, escrito quando os módulos moravam soltos na raiz.
    Em 09/09/2026 eles viraram o pacote ``isocentro/`` e o glob passou a
    ver só os três ``run_*.py``: as três travas deste arquivo ficaram VERDES e
    inertes por uma semana — achado em 16/09, no corte 4 da R-06. Trava que não
    olha nada passa sempre, e é por isso que ``TestAVarreduraVeOPrograma``
    existe.
    """
    return sorted(p for p in (RAIZ / "isocentro").rglob("*.py")
                  if p.name not in FONTES_DO_PADRAO)


def _texto(p: Path) -> str:
    """Lê tolerando o BOM — ``posicionamento.py`` tem um."""
    return p.read_text(encoding="utf-8-sig")


class TestAVarreduraVeOPrograma(unittest.TestCase):
    """A guarda da guarda: as travas abaixo só valem se ``_modulos`` achar o
    programa. Mudar o pacote de lugar de novo tem de REPROVAR aqui, e não
    deixar as outras passando sobre uma lista vazia."""

    def test_as_telas_estao_na_varredura(self):
        nomes = {p.name for p in _modulos()}
        for tela in ("gui.py", "capa.py", "fichinha.py", "tratamento.py"):
            self.assertIn(tela, nomes, f"a varredura não vê {tela}")

    def test_e_as_regras_ainda_mordem(self):
        """Controle positivo: o ``estilo.py`` é todo hexadecimal. Se a regra
        não o achasse, ela não acharia o desvio de ninguém."""
        estilo = fontes.caminho("estilo.py")
        self.assertTrue(any(_HEX.search(ln) for ln in _texto(estilo).splitlines()
                            if not ln.lstrip().startswith("#")))


class TestJanelasEDialogos(unittest.TestCase):

    def test_toda_janela_propria_herda_de_ui_Dialogo(self):
        """``QDialog`` cru volta ao ponto de partida: rodapé escrito à mão.

        Eram 14 assim, e os dois botões trocavam de lugar entre telas —
        ``[Confirmar][Cancelar]`` em cinco, o inverso em três. Quem acabou de
        clicar "Aplicar" à direita numa encontrava "Cancelar" naquela posição
        na seguinte. O ``ui.Dialogo`` fechou isso; esta trava impede a 15ª.
        """
        achados = []
        for p in _modulos():
            arvore = ast.parse(_texto(p))
            for no in ast.walk(arvore):
                if not isinstance(no, ast.ClassDef):
                    continue
                bases = {ast.unparse(b) for b in no.bases}
                if "QDialog" not in bases:
                    continue
                if f"{p.name}:{no.name}" in EXCECOES:
                    continue
                achados.append(f"{p.name}:{no.lineno} {no.name}")
        self.assertEqual(
            achados, [],
            "janela própria fora do padrão — herde de ``ui.Dialogo`` e monte o "
            "rodapé com ``rodape(...)``; se a fuga for deliberada, escreva o "
            "motivo em EXCECOES:\n  " + "\n  ".join(achados))

    def test_nenhuma_aba_nasce_crua(self):
        """``QTabWidget()`` sem ``estilizar_abas`` é a barra do sistema.

        A Administração e o Formulário ficaram assim ao lado das abas
        estilizadas do Posicionamento — na MESMA janela. E não é só cara: a
        fonte da barra tem de ser posta no widget, senão o Qt mede a aba com
        uma fonte e a desenha com outra, e o nome do setup sai cortado nas
        duas pontas. ``ui.abas()`` faz os dois passos.
        """
        achados = []
        for p in _modulos():
            for i, linha in enumerate(_texto(p).splitlines(), 1):
                if re.search(r"\bQTabWidget\s*\(", linha):
                    achados.append(f"{p.name}:{i} {linha.strip()}")
        self.assertEqual(
            achados, [],
            "aba montada fora do padrão — use ``ui.abas(...)``:\n  "
            + "\n  ".join(achados))


class TestCorDeTela(unittest.TestCase):

    def test_nenhuma_cor_de_tela_e_hexadecimal_cru(self):
        """Cor escrita à mão não acompanha a troca dia↔noite.

        Ela não some no modo em que foi escrita — some no OUTRO, e quem
        trabalha no escuro é quem encontra o rótulo cinza sobre fundo cinza. A
        paleta mora no ``estilo``; papel e gráfico são outra coisa, e estão em
        ``HEX_PERMITIDO`` com o motivo.
        """
        achados = []
        for p in _modulos():
            if p.name in HEX_PERMITIDO:
                continue
            for i, linha in enumerate(_texto(p).splitlines(), 1):
                if linha.lstrip().startswith("#"):
                    continue          # comentário: hex citado é explicação
                if _HEX.search(linha):
                    achados.append(f"{p.name}:{i} {linha.strip()}")
        self.assertEqual(
            achados, [],
            "cor de tela escrita à mão — pegue-a do ``estilo`` e aplique com "
            "``estilo.pintar``; se for cor de papel ou de gráfico, declare o "
            "arquivo em HEX_PERMITIDO com o motivo:\n  " + "\n  ".join(achados))


def _repinturas_divergentes(fonte: str) -> list[str]:
    """Widget registrado no ``pintar`` com UMA receita e repintado direto com
    OUTRA. Devolve ``linha classe alvo`` de cada ``setStyleSheet`` assim.

    Só olha alvos ``self`` e ``self.x``, dentro da mesma classe: é onde o
    registro e a repintura se encontram por nome. Variável de laço (``btn``,
    ``b``) muda de nome entre os dois lugares e daria alarme falso.

    Repintura IGUAL à receita é o jeito certo de dizer "o estado mudou":
    ``pintar(self.x, self._folha)`` com ``self.x.setStyleSheet(self._folha())``,
    ou a lambda com o mesmo corpo da chamada direta.
    """
    arvore = ast.parse(fonte)
    registros: dict[tuple[str, str], list[ast.AST]] = {}
    diretas: list[tuple[str, str, ast.Call]] = []

    def visitar(no: ast.AST, classe: str) -> None:
        if isinstance(no, ast.ClassDef):
            classe = no.name
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
            alvo = no.func.value if no.func.attr == "setStyleSheet" else (
                no.args[0] if no.func.attr == "pintar" and len(no.args) == 2
                else None)
            if alvo is not None:
                nome = ast.unparse(alvo)
                if nome == "self" or re.fullmatch(r"self\.\w+", nome):
                    if no.func.attr == "pintar":
                        registros.setdefault((classe, nome), []).append(no.args[1])
                    elif len(no.args) == 1:
                        diretas.append((classe, nome, no))
        for filho in ast.iter_child_nodes(no):
            visitar(filho, classe)

    visitar(arvore, "")

    def igual(receita: ast.AST, expr: ast.AST) -> bool:
        if isinstance(receita, ast.Lambda):
            return ast.dump(receita.body) == ast.dump(expr)
        return (isinstance(expr, ast.Call) and not expr.args and not expr.keywords
                and ast.dump(expr.func) == ast.dump(receita))

    achados = []
    for classe, nome, no in diretas:
        receitas = registros.get((classe, nome))
        if receitas and not any(igual(r, no.args[0]) for r in receitas):
            achados.append(f"{no.lineno} {classe} {nome}")
    return achados


class TestRepinturaSegueAReceita(unittest.TestCase):

    def test_repintura_direta_usa_a_receita_registrada(self):
        """O ``pintar`` refaz a folha a cada troca dia↔noite pela RECEITA que
        guardou — e desfaz, em silêncio, a folha que outro caminho pôs direto.

        A dica do Posicionamento ficava âmbar quando avisava que fotos não
        seriam impressas; a receita registrada era o cinza de dica comum. Na
        troca de modo o alerta voltava a cinza (medido em 17/09/2026: #E0A63A
        → #8A95A1), com o aviso ainda ligado. A receita tem de LER o estado; a
        repintura só a reaplica.
        """
        achados = [f"{p.name}:{a}" for p in _modulos()
                   for a in _repinturas_divergentes(_texto(p))]
        self.assertEqual(
            achados, [],
            "folha aplicada direto num widget que o ``pintar`` repinta com "
            "OUTRA receita — a troca dia↔noite desfaz esta. Ponha o estado "
            "dentro da receita e reaplique ``self.x.setStyleSheet("
            "self._folha())``:\n  " + "\n  ".join(achados))

    def test_e_a_regra_morde(self):
        """Controle positivo, e o negativo que evita alarme falso."""
        fonte = (
            "class A:\n"
            "    def __init__(self):\n"
            "        st.pintar(self.x, lambda: f'color:{st.TEXTO}')\n"
            "        st.pintar(self.y, self._folha)\n"
            "        st.pintar(btn, lambda b=btn: st.btn_solido())\n"
            "    def mudar(self):\n"
            "        self.x.setStyleSheet(f'color:{st.AMBAR}')\n"
            "        self.y.setStyleSheet(self._folha())\n"
            "        btn.setStyleSheet(st.btn_contorno())\n"
            "class B:\n"
            "    def f(self):\n"
            "        self.x.setStyleSheet(f'color:{st.AMBAR}')\n")
        self.assertEqual(_repinturas_divergentes(fonte), ["7 A self.x"])


def _verde(cor) -> bool:
    """Matiz de verde (75° a 165°) com saturação e brilho que se leem como cor.

    O ciano da severidade informativa fica em ~186°, fora; o verde-azulado de
    antes da R-23 (#0F7B7B) fica em 180°. Um cinza esverdeado de saturação
    baixa não é sinal de nada e não é pego.
    """
    import colorsys
    if isinstance(cor, str):
        h = cor.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    else:
        r, g, b = cor
    hue, sat, val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 75 <= hue * 360 <= 165 and sat >= 0.25 and val >= 0.2


# Onde a isodose é desenhada, e portanto onde ``DOSE`` pode aparecer.
ARQUIVOS_DA_DOSE = {"corte.py", "visualizador.py", "dvh.py", "grafico_dvh.py"}
_USO_DOSE = re.compile(r"\b(?:st|estilo)\.DOSE\b")
_QCOLOR_LITERAL = re.compile(r"QColor\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


class TestVerdeEDose(unittest.TestCase):
    """Verde é dose (DESIGN.md, Colors; EXPERIENCE.md, Migração). A tela mostra
    isodose ao lado dos botões; um botão, um "ok" ou um brilho verde ensinariam
    o olho a ler verde como "tudo certo" — inclusive em cima da dose. Até a
    R-23 havia dois: o brilho do ``ui.botao(brilho=True)`` e o do botão de
    Impressão, ambos ``QColor(85, 211, 145)``, que nenhuma trava de hexadecimal
    pegava."""

    def test_nenhuma_chave_da_paleta_e_verde_fora_da_dose(self):
        from isocentro.interface import estilo
        for nome, paleta in estilo.MODOS.items():
            for chave, valor in paleta.items():
                with self.subTest(modo=nome, chave=chave):
                    if chave == "DOSE":
                        self.assertTrue(_verde(valor), "a dose deixou de ser verde")
                    else:
                        self.assertFalse(_verde(valor),
                                         f"{chave} = {valor} é verde")

    def test_dose_so_onde_ha_isodose(self):
        achados = [f"{p.name}:{i}" for p in _modulos()
                   if p.name not in ARQUIVOS_DA_DOSE
                   for i, linha in enumerate(_texto(p).splitlines(), 1)
                   if _USO_DOSE.search(linha)]
        self.assertEqual(achados, [], "DOSE fora do desenho de isodose")

    def test_nenhum_qcolor_verde_escrito_a_mao(self):
        achados = []
        for p in _modulos() + [RAIZ / "isocentro/interface/ui.py"]:
            if p.name in HEX_PERMITIDO or p.name in ARQUIVOS_DA_DOSE:
                continue
            for i, linha in enumerate(_texto(p).splitlines(), 1):
                for m in _QCOLOR_LITERAL.finditer(linha):
                    if _verde(tuple(int(x) for x in m.groups())):
                        achados.append(f"{p.name}:{i} {linha.strip()}")
        self.assertEqual(achados, [], "QColor verde fora da isodose")

    def test_e_a_regra_morde(self):
        self.assertTrue(_verde((85, 211, 145)))
        self.assertTrue(_verde("#3DDC84"))
        self.assertFalse(_verde("#2CCFE0"))   # ciano da severidade info
        self.assertFalse(_verde("#0F7B7B"))   # o acento de antes da R-23
        self.assertFalse(_verde("#93A3B6"))   # estado neutro


class TestAsExcecoesContinuamValendo(unittest.TestCase):
    """Exceção vencida é pior que exceção nenhuma: ninguém questiona o que
    está escrito. Mesma família do "EM ABERTO" já resolvido no ``NOTAS.md``."""

    def test_toda_excecao_ainda_existe(self):
        for chave in EXCECOES:
            arquivo, nome = chave.split(":")
            with self.subTest(excecao=chave):
                caminho = fontes.caminho(arquivo)
                self.assertTrue(caminho.exists(), f"{arquivo} não existe mais")
                self.assertIn(f"class {nome}(", _texto(caminho),
                              f"{chave} já não existe — tire da lista")

    def test_todo_arquivo_de_HEX_PERMITIDO_ainda_usa_hex(self):
        for arquivo in HEX_PERMITIDO:
            with self.subTest(arquivo=arquivo):
                caminho = fontes.caminho(arquivo)
                self.assertTrue(caminho.exists(), f"{arquivo} não existe mais")
                self.assertTrue(
                    _HEX.search(_texto(caminho)),
                    f"{arquivo} já não tem hexadecimal — tire da lista")


if __name__ == "__main__":
    unittest.main()
