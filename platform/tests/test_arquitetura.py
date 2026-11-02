"""A direção de dependência como TESTE, e não como texto (AD-22 da espinha).

A espinha (``docs/planejamento/sistema-global/architecture-isocentro-2026-10-19/
ARCHITECTURE-SPINE.md``) escreve quem pode importar quem: a tela age pelos
módulos, o módulo usa o núcleo e o ``rt``, o adaptador implementa as portas do
núcleo, e o núcleo não conhece nenhum deles. Até 23/10/2026 isso era só texto, e
o texto já tinha perdido: o ``dominio/`` — "a regra e o cálculo, sem interface
nenhuma", segundo o próprio ``CLAUDE.md`` — importava ``PyQt5`` em dois arquivos
e a ``interface`` em dois, e o ``banco`` importava a ``interface``. Ninguém
discordou da regra; ninguém foi avisado de que a estava quebrando. Estes testes
leem o CÓDIGO-FONTE por ``ast`` (o import tardio, dentro de função, conta igual:
é por ele que as quatro violações entraram) e reprovam no lugar onde custa
segundos.

**Três grupos de regra:**

- **AD-22, ligadas.** Escritas sobre os pacotes-ALVO (``nucleo/``, ``modulos/``,
  ``interface/modulos/``, ``composicao.py``), que hoje não existem e passam
  vazias — e mordem no primeiro arquivo que nascer lá. Para os pacotes de hoje,
  só o que a espinha diagnosticou ("Contradições com o código atual"): o
  ``dominio/`` não importa Qt nem tela; a borda (``banco/``, ``adaptadores/``)
  não importa Qt nem tela.
- **AD-38 (``rt/``), desligadas** até a R-58 terminar a divisão do ``dicom/``:
  acende com ``R58_FEITA = True``.
- **AD-40 (manifesto e raiz de composição), desligadas** até a R-60: acende com
  ``R60_FEITA = True``.

Regra desligada não roda sobre o pacote, mas o controle positivo dela roda
sempre, sobre fonte sintética: trava que ninguém executa apodrece calada, e só se
descobriria no dia de acender.

**O que este arquivo ainda NÃO cobre**, de propósito (a espinha não o
diagnosticou, e transformar cada um em exceção seria decidir por ela o mapa do
código de hoje para as camadas de amanhã): a ``interface/`` de hoje importa o
``banco`` (23 lugares) e os ``adaptadores`` (3), porque ela ainda é a tela E o
módulo; o ``dominio/gatilho.py`` e o ``gatilho_registro.py`` importam ``banco`` e
``adaptadores``; o ``dados/`` importa o ``banco``; e a gravação em tabela de outro
dono (AD-27) espera o registro tabela → dono existir. A regra de "tela não importa
adaptador nem banco" já vale para ``interface/modulos/``.

**Exceção** é uma entrada em ``EXCECOES``: arquivo e família proibida, com a data
de entrada, a frente que a tira (ou o que a tiraria, quando não há frente) e o
motivo. Exceção vencida reprova: ninguém questiona o que está escrito.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "isocentro"
CLASSIFICACAO = RAIZ / "docs" / "qms" / "classificacao-62304.md"

# Os interruptores. Quem fecha a frente vira o seu para True no MESMO commit, e
# o que aparecer vermelho é a lista do que a frente ainda deixou para trás.
R58_FEITA = False   # AD-38: ``rt/`` puro, núcleo e borda sem ``rt``
R60_FEITA = False   # AD-40: MANIFESTO e raiz de composição única

# Todo binding de Qt, e não só o de hoje e o do porte (AD-36): um ``PyQt6`` ou
# um ``qtpy`` no domínio carrega o Qt do mesmo jeito.
QT = frozenset({"PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "sip"})
# O ``rt`` por LISTA PERMITIDA (AD-38: "importa só bibliotecas externas
# (pydicom, numpy) e a si mesmo"): fora delas, só a biblioteca padrão, menos o
# que é arquivo, rede, banco, processo, cache ou estado. Por lista proibida,
# cada módulo esquecido (``subprocess``, ``codecs.open``) passava calado. ``io``
# também sai: ``BytesIO`` para o ``dcmread`` é leitura, e leitura é do
# adaptador. ``builtins.open`` é a chamada solta a ``open(``, que
# ``_dependencias`` registra como se fosse import. Hoje quem segura o ``rt`` é
# o ``test_rt_margem`` (a mesma ideia, para o ``margem.py``); a regra daqui
# acende na R-58.
RT_EXTERNOS = frozenset({"numpy", "pydicom"})
RT_PADRAO_PROIBIDO = frozenset({
    "os", "pathlib", "shutil", "zipfile", "tarfile", "glob", "tempfile", "io",
    "codecs", "pickle", "shelve", "dbm", "sqlite3", "fileinput", "mmap",
    "socket", "ssl", "http", "urllib", "smtplib", "ftplib", "asyncio",
    "subprocess", "multiprocessing", "threading", "concurrent", "logging",
    "importlib", "pkgutil", "builtins.open", "functools.lru_cache",
    "functools.cache", "functools.cached_property"})


@dataclass(frozen=True)
class Excecao:
    desde: str      # dd/mm/aaaa
    saida: str      # a frente que a tira, ou o que a tiraria
    motivo: str


# Chave: (arquivo relativo a ``isocentro/``, o que ele importa — prefixo com
# ponto). Tão estreita quanto o motivo: a exceção do ``capa_dados`` é para o
# ``interface.simulacao`` e para nada mais; um ``from isocentro.interface
# import gui`` no mesmo arquivo amanhã reprova.
EXCECOES = {
    ("dominio/qualidade_metodo.py", "PySide6"): Excecao(
        "23/10/2026", "R-32",
        "é um widget (o painel de método da aba Qualidade) morando em "
        "``dominio/``; a R-32 tira a aba do Radioteraficha e o cálculo vira "
        "verificação ``plano.*``"),
    ("dominio/qualidade_metodo.py", "isocentro.interface.estilo"): Excecao(
        "23/10/2026", "R-32", "o mesmo widget, pintado com ``interface.estilo``"),
    ("dominio/qualidade_metodo.py", "isocentro.interface.ui"): Excecao(
        "23/10/2026", "R-32", "o mesmo widget, montado com ``interface.ui``"),
    ("dominio/gatilho.py", "isocentro.interface.simulacao"): Excecao(
        "23/10/2026",
        "sem frente: sai quando a raiz das simulações deixar "
        "``interface/simulacao.py``",
        "import tardio de ``interface.simulacao`` para achar a pasta do "
        "cadastro de simulação (``simulacao.raiz()``), que não é tela"),
    ("banco/capa_dados.py", "isocentro.interface.simulacao"): Excecao(
        "23/10/2026",
        "sem frente: sai quando ``ARQ_NOTA``, ``ARQ_CADASTRO`` e a raiz das "
        "simulações deixarem ``interface/simulacao.py``",
        "quatro imports tardios de ``interface.simulacao`` pelos nomes de "
        "arquivo do cadastro, que não são tela"),
}

# As do AD-38 (espinha, AD-22: "e, com o AD-38, ..."). Separadas porque só
# valem com a regra acesa: com ela desligada, ninguém as confere.
EXCECOES_RT = {
    ("banco/capa_dados.py", "isocentro.dicom.dicom_rt"): Excecao(
        "23/10/2026", "R-58",
        "a borda lendo o RT Plan com o ``dicom_rt`` para montar a capa"),
    ("banco/tratamento_db.py", "isocentro.dicom.dicom_rt"): Excecao(
        "23/10/2026", "R-58",
        "a borda usando o ``dicom_rt`` ao casar o tratamento"),
    ("papel/capa_pdf.py", "isocentro.banco.capa_dados"): Excecao(
        "23/10/2026", "sem frente: ``papel/`` é travado",
        "quem imprime a capa importa ``banco.capa_dados`` direto, sem fachada"),
}


@dataclass(frozen=True)
class Regra:
    nome: str
    vale_para: Callable[[str], bool]           # lugar: caminho sob ``isocentro/``
    proibe: Callable[[str, str], Optional[str]]  # (lugar, importado) -> família


def _familia(nome: str) -> str:
    """``isocentro.banco.capa_db.ler`` → ``isocentro.banco``; ``PyQt5.QtCore`` →
    ``Qt``; ``os.path`` → ``os``. É a unidade da REGRA; a da exceção é mais
    estreita (o prefixo do nome importado, ver ``EXCECOES``)."""
    partes = nome.split(".")
    if partes[0] in QT:
        return "Qt"
    if partes[0] == "isocentro":
        return ".".join(partes[:2])
    return partes[0]


def _em(*familias: str) -> Callable[[str, str], Optional[str]]:
    """Proíbe as famílias dadas. Aceita também nome com ponto do lado de fora do
    pacote (``functools.lru_cache``), que casa pelo prefixo."""
    def proibe(_lugar: str, nome: str) -> Optional[str]:
        fam = _familia(nome)
        if fam in familias:
            return fam
        for f in familias:
            if "." in f and not f.startswith("isocentro.") and (
                    nome == f or nome.startswith(f + ".")):
                return f
        return None
    return proibe


def _comeca(*prefixos: str) -> Callable[[str], bool]:
    return lambda lugar: lugar.startswith(prefixos)


def _modulo_alheio(lugar: str, nome: str) -> Optional[str]:
    """Módulo importando outro módulo. A fachada ``consulta`` do outro é a única
    porta (AD-3): ``from isocentro.modulos.plano import consulta`` passa,
    ``from isocentro.modulos import plano`` não."""
    partes = nome.split(".")
    if partes[:2] != ["isocentro", "modulos"] or len(partes) < 3:
        return None
    meu = lugar.split("/")[1] if lugar.count("/") >= 2 else ""
    if partes[2] == meu:
        return None
    if len(partes) >= 4 and partes[3] == "consulta":
        return None
    return f"isocentro.modulos.{partes[2]}"


def _fora_do_rt(_lugar: str, nome: str) -> Optional[str]:
    topo = nome.split(".")[0]
    if topo == "isocentro":
        fam = _familia(nome)
        return None if fam == "isocentro.rt" else fam
    if topo in RT_EXTERNOS or topo == "__future__":
        return None
    for p in RT_PADRAO_PROIBIDO:
        if nome == p or nome.startswith(p + "."):
            return p
    if topo in sys.stdlib_module_names:
        return None
    return _familia(nome)   # externa fora da lista: PIL, matplotlib, Qt, ...


def _fora_da_composicao(_lugar: str, nome: str) -> Optional[str]:
    """A raiz de composição importa só ``modulos/*`` e o núcleo, e lista os
    módulos à mão: ``importlib``/``pkgutil`` ali é descoberta por pasta (AD-40).

    O núcleo entra pelo AD-2 ("importa só ``modulos/*`` e núcleo"); o texto do
    AD-40 diz só ``modulos/*``. Fica o mais largo dos dois até a R-60 dizer
    qual vale — é ela que escreve a ``composicao.py``."""
    fam = _familia(nome)
    if fam in ("importlib", "pkgutil"):
        return fam
    if fam.startswith("isocentro.") and fam not in ("isocentro.modulos",
                                                    "isocentro.nucleo"):
        return fam
    return None


REGRAS_AD22 = (
    Regra("AD-22: o núcleo não importa Qt, tela, módulo nem adaptador",
          _comeca("nucleo/"),
          _em("Qt", "isocentro.interface", "isocentro.modulos",
              "isocentro.adaptadores", "isocentro.banco")),
    Regra("AD-22: o módulo não importa Qt, tela nem adaptador",
          _comeca("modulos/"),
          _em("Qt", "isocentro.interface", "isocentro.adaptadores",
              "isocentro.banco")),
    Regra("AD-22: o módulo não importa outro módulo, fora da fachada de consulta",
          _comeca("modulos/"), _modulo_alheio),
    Regra("AD-22: a tela de módulo não importa adaptador nem banco",
          _comeca("interface/modulos/"),
          _em("isocentro.adaptadores", "isocentro.banco")),
    Regra("AD-22: a raiz de composição não importa tela",
          lambda lugar: lugar == "composicao.py",
          _em("Qt", "isocentro.interface")),
    # As duas abaixo são o mapa da espinha para os pacotes de HOJE.
    Regra("AD-22: o domínio não importa Qt nem tela",
          _comeca("dominio/"), _em("Qt", "isocentro.interface")),
    Regra("AD-22: a borda (banco, adaptadores) não importa Qt nem tela",
          _comeca("banco/", "adaptadores/"), _em("Qt", "isocentro.interface")),
)

REGRAS_AD38 = (
    Regra("AD-38: o rt não importa outro pacote, Qt, banco, rede, arquivo, "
          "estado nem desenho",
          _comeca("rt/"), _fora_do_rt),
    Regra("AD-38: núcleo e borda não importam o rt (o adaptador devolve o "
          "Dataset cru)",
          _comeca("nucleo/", "adaptadores/", "banco/"),
          _em("isocentro.rt", "isocentro.dicom")),
    Regra("AD-38: quem imprime não importa a borda",
          _comeca("papel/"), _em("isocentro.banco", "isocentro.adaptadores")),
)

REGRAS_AD40 = (
    Regra("AD-40: a raiz de composição importa só modulos/* e o núcleo, sem "
          "descoberta",
          lambda lugar: lugar == "composicao.py", _fora_da_composicao),
    Regra("AD-40: a lista de telas não descobre tela por pasta",
          lambda lugar: lugar == "interface/composicao.py",
          _em("importlib", "pkgutil")),
)


# ── Leitura ─────────────────────────────────────────────────────────────────

def _texto(p: Path) -> str:
    """Lê tolerando o BOM — ``posicionamento.py`` tem um."""
    return p.read_text(encoding="utf-8-sig")


def _arquivos():
    """Os ``.py`` do pacote, como (lugar, caminho), lugar relativo a
    ``isocentro/`` e com barra normal."""
    return sorted((p.relative_to(PACOTE).as_posix(), p)
                  for p in PACOTE.rglob("*.py"))


def _dependencias(lugar: str, arvore: ast.AST):
    """(linha, nome absoluto) de cada dependência do arquivo, em qualquer
    profundidade: o import tardio dentro de função é exatamente como as quatro
    violações do AD-22 entraram, e um teste que olhasse só o topo as perderia.

    ``from X import a`` vira ``X.a`` (e não ``X`` também): é o que separa
    ``from isocentro.modulos.plano import consulta``, a fachada, de importar o
    módulo inteiro. ``importlib.import_module("...")`` com texto fixo conta como
    import; ``open(`` solto conta como ``builtins.open``.
    """
    pacote = ["isocentro", *lugar.split("/")[:-1]]
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for a in no.names:
                yield no.lineno, a.name
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                base = pacote[:len(pacote) - (no.level - 1)]
                modulo = ".".join(base + ([no.module] if no.module else []))
            else:
                modulo = no.module or ""
            for a in no.names:
                yield no.lineno, modulo if a.name == "*" else f"{modulo}.{a.name}"
        elif isinstance(no, ast.Call):
            alvo = ast.unparse(no.func)
            if alvo in ("importlib.import_module", "import_module",
                        "__import__") and no.args and isinstance(
                            no.args[0], ast.Constant) and isinstance(
                                no.args[0].value, str):
                yield no.lineno, no.args[0].value
            elif alvo == "open":
                yield no.lineno, "builtins.open"


def _achados(regras, fontes):
    """(lugar, família, linha, nome, regra) de cada dependência proibida.
    ``fontes`` é [(lugar, texto)] — do disco ou sintético, para o controle."""
    saida = []
    for lugar, texto in fontes:
        aplicaveis = [r for r in regras if r.vale_para(lugar)]
        if not aplicaveis:
            continue
        for linha, nome in _dependencias(lugar, ast.parse(texto)):
            for r in aplicaveis:
                fam = r.proibe(lugar, nome)
                if fam:
                    saida.append((lugar, fam, linha, nome, r.nome))
    return saida


def _do_pacote():
    return [(lugar, _texto(p)) for lugar, p in _arquivos()]


def _casa(achado, chave) -> bool:
    """O achado é o que a exceção ``(arquivo, prefixo)`` libera?"""
    lugar, _fam, _linha, nome, _regra = achado
    arquivo, prefixo = chave
    return lugar == arquivo and (nome == prefixo or nome.startswith(prefixo + "."))


def _fora_das_excecoes(achados, excecoes):
    return [a for a in achados if not any(_casa(a, k) for k in excecoes)]


def _relatorio(achados) -> str:
    return "\n  ".join(f"{lugar}:{linha} importa {nome}  [{regra}]"
                       for lugar, _fam, linha, nome, regra in achados)


# ── AD-40: manifesto e raiz de composição ───────────────────────────────────

def _manifesto(texto: str):
    """Os campos do ``MANIFESTO`` de um ``__init__.py``, como dict de valores
    literais; ``None`` se ele não existe. Aceita ``Manifesto(nome=..., ...)`` e
    ``{"nome": ...}`` — o tipo é da R-60, e o teste não deve fixar a forma
    antes dela. Campo que não é literal fica de fora (e o problema sai como
    "nome é None", que é verdade para quem lê o arquivo sem rodá-lo).
    Argumento posicional vira o campo ``"_posicional"``: o teste não adivinha a
    ordem dos campos, e o problema diz para nomeá-los."""
    for no in ast.parse(texto).body:
        if isinstance(no, (ast.Assign, ast.AnnAssign)):
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            if not any(isinstance(t, ast.Name) and t.id == "MANIFESTO"
                       for t in alvos):
                continue
            if no.value is None:          # ``MANIFESTO: Manifesto`` sem valor
                return None
            pares = []
            campos = {}
            if isinstance(no.value, ast.Call):
                pares = [(k.arg, k.value) for k in no.value.keywords if k.arg]
                if no.value.args:
                    campos["_posicional"] = True
            elif isinstance(no.value, ast.Dict):
                pares = [(k.value, v) for k, v in zip(no.value.keys, no.value.values)
                         if isinstance(k, ast.Constant)]
            for chave, valor in pares:
                try:
                    campos[chave] = ast.literal_eval(valor)
                except (ValueError, TypeError, SyntaxError, MemoryError,
                        RecursionError):
                    pass
            return campos
    return None


def _modulos_importados(texto: str, prefixo: str, lugar: str) -> set:
    """Os nomes ``<m>`` de ``prefixo.<m>`` que a fonte importa. ``lugar`` é o
    arquivo de onde ela vem: o ``from .modulos import plano`` da
    ``interface/composicao.py`` é ``isocentro.interface.modulos.plano``."""
    saida = set()
    for _linha, nome in _dependencias(lugar, ast.parse(texto)):
        if nome.startswith(prefixo + "."):
            saida.add(nome[len(prefixo) + 1:].split(".")[0])
    return saida


def _classes_atribuidas(tabela: str):
    """(``<m>`` → classe, conflitos), das linhas do ``classificacao-62304.md``
    cuja primeira célula ABRE com o pacote entre crases. Quem decide a classe é
    o físico; aqui só se lê.

    Só a primeira menção conta: a tabela já tem linhas como "`dominio/ritmo`
    (… compartilhado por Ficha Virtual, Capa …)", e uma "`modulos/indicadores`
    (lê a fachada de `modulos/plano`) | A" daria ao Plano a classe A — a classe
    rebaixada que o AD-39 proíbe. O mesmo módulo em duas linhas com classes
    diferentes é conflito, e conflito o teste relata em vez de escolher."""
    classes, conflitos = {}, []
    for linha in tabela.splitlines():
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if len(celulas) < 2:
            continue
        primeira = re.search(r"`([^`]+)`", celulas[0])
        achado = primeira and re.fullmatch(r"modulos/([a-z_]+)/?", primeira.group(1))
        if not achado:
            continue
        m = achado.group(1)
        if m in classes and classes[m] != celulas[1]:
            conflitos.append(m)
        classes[m] = celulas[1]
    return classes, conflitos


def _problemas_da_composicao(modulos: dict, composicao: Optional[str],
                             telas: Optional[str], tabela: str) -> list:
    """O que o AD-40 reprova. ``modulos``: ``<m>`` → texto do ``__init__.py``;
    ``composicao`` e ``telas``: texto de ``isocentro/composicao.py`` e de
    ``interface/composicao.py`` (``None`` = não existe)."""
    # Sem retorno antecipado quando não há módulo: uma lista de telas cheia
    # sobre ``modulos/`` vazio é justamente o caso em que TODA tela é órfã.
    problemas = []
    listados = _modulos_importados(composicao or "", "isocentro.modulos",
                                   "composicao.py")
    com_tela = _modulos_importados(telas or "", "isocentro.interface.modulos",
                                   "interface/composicao.py")
    classes, conflitos = _classes_atribuidas(tabela)
    for m in conflitos:
        problemas.append(f"classificacao-62304.md: modulos/{m} em duas linhas "
                         "com classes diferentes")
    for m, texto in sorted(modulos.items()):
        if m not in listados:
            problemas.append(f"modulos/{m} fora da lista de isocentro/composicao.py")
        man = _manifesto(texto)
        if man is None:
            problemas.append(f"modulos/{m}/__init__.py sem MANIFESTO")
            continue
        if man.get("_posicional"):
            problemas.append(f"modulos/{m}: MANIFESTO com argumento posicional — "
                             "nomeie os campos (nome=, classe=, ...)")
        if man.get("nome") != m:
            problemas.append(f"modulos/{m}: MANIFESTO.nome é {man.get('nome')!r}")
        if m not in com_tela:
            problemas.append(f"modulos/{m}: manifesto sem tela em interface/composicao.py")
        verificacoes = man.get("verificacoes", ())
        if isinstance(verificacoes, str):   # seria conferido letra por letra
            verificacoes = (verificacoes,)
            problemas.append(f"modulos/{m}: verificacoes é texto, não lista")
        for v in verificacoes:
            if not str(v).startswith(f"{m}."):
                problemas.append(f"modulos/{m}: verificação {v!r} sem o prefixo {m}.")
        # Sem linha no classificacao-62304.md, vale rigor C (AD-39).
        esperada = classes.get(m, "C")
        if man.get("classe") != esperada:
            problemas.append(f"modulos/{m}: classe {man.get('classe')!r} no manifesto, "
                             f"{esperada!r} no classificacao-62304.md")
    for m in sorted(com_tela - set(modulos)):
        problemas.append(f"interface/composicao.py: tela de {m} sem módulo/manifesto")
    return problemas


def _composicao_do_disco():
    pasta = PACOTE / "modulos"
    modulos = {}
    if pasta.is_dir():
        for p in sorted(pasta.iterdir()):
            if (p / "__init__.py").is_file():
                modulos[p.name] = _texto(p / "__init__.py")

    def ler(p):
        return _texto(p) if p.is_file() else None
    tabela = _texto(CLASSIFICACAO) if CLASSIFICACAO.is_file() else ""
    return (modulos, ler(PACOTE / "composicao.py"),
            ler(PACOTE / "interface" / "composicao.py"), tabela)


# ── Os testes ───────────────────────────────────────────────────────────────

class TestAVarreduraVeOPrograma(unittest.TestCase):
    """A guarda da guarda (mesma razão do ``test_padrao_visual``: em 09/09/2026
    as travas de lá ficaram uma semana verdes sobre uma lista vazia)."""

    def test_o_pacote_esta_na_varredura(self):
        lugares = {lugar for lugar, _p in _arquivos()}
        for lugar in ("dominio/gatilho.py", "banco/capa_dados.py",
                      "rt/margem.py", "adaptadores/dicom/leitura.py",
                      "interface/gui.py"):
            self.assertIn(lugar, lugares)

    def test_o_import_tardio_e_o_relativo_sao_vistos(self):
        fonte = ("def f():\n    from isocentro.interface import ui\n"
                 "from ..interface import estilo\n"
                 "from . import vizinho\n")
        deps = {n for _l, n in _dependencias("dominio/x.py", ast.parse(fonte))}
        self.assertEqual(deps, {"isocentro.interface.ui",
                                "isocentro.interface.estilo",
                                "isocentro.dominio.vizinho"})


class TestDirecaoDeDependencia(unittest.TestCase):

    def test_nenhuma_dependencia_proibida_fora_das_excecoes(self):
        """A regra que vale hoje. Ao cair aqui: ou o import muda de lugar (o
        dado sobe por parâmetro, a tela chama o módulo), ou ele entra em
        ``EXCECOES`` com data, saída e motivo — exceção escrita é decisão;
        import calado é a divergência de volta."""
        novos = _fora_das_excecoes(_achados(REGRAS_AD22, _do_pacote()), EXCECOES)
        self.assertEqual(novos, [], "dependência proibida:\n  " + _relatorio(novos))

    def test_as_regras_mordem(self):
        """Controle positivo, um caso por regra, sobre fonte sintética: os
        pacotes-alvo ainda não existem, e regra que nunca achou nada não
        prova que acharia."""
        casos = [
            ("nucleo/motor.py", "from PyQt5.QtCore import QTimer"),
            ("nucleo/motor.py", "from isocentro.adaptadores.dicom import rede"),
            ("modulos/plano/regras.py", "import isocentro.banco.capa_db"),
            ("modulos/plano/regras.py", "from isocentro.modulos import tratamento"),
            ("interface/modulos/plano/tela.py", "from isocentro.banco import capa_db"),
            ("composicao.py", "from isocentro.interface import gui"),
            ("dominio/x.py", "from PySide6.QtWidgets import QLabel"),
            ("dominio/x.py", "from PyQt6.QtCore import QTimer"),
            ("dominio/x.py", "from qtpy import QtWidgets"),
            ("adaptadores/x.py", "from isocentro.interface import ui"),
        ]
        for lugar, fonte in casos:
            with self.subTest(lugar=lugar, fonte=fonte):
                self.assertTrue(_achados(REGRAS_AD22, [(lugar, fonte)]))

    def test_o_que_a_regra_permite(self):
        """O outro lado: a fachada de consulta, o próprio módulo, o ``rt`` e o
        núcleo. Uma regra que reprovasse a fachada empurraria quem precisa dela
        para a exceção, e a lista viraria ruído."""
        casos = [
            ("modulos/plano/regras.py", "from isocentro.modulos.tratamento import consulta"),
            ("modulos/plano/regras.py", "from isocentro.modulos.tratamento.consulta import x"),
            ("modulos/plano/regras.py", "from isocentro.modulos.plano import dados"),
            ("modulos/plano/regras.py", "from isocentro.rt import margem"),
            ("modulos/plano/regras.py", "from isocentro.nucleo import gravar"),
            ("interface/modulos/plano/tela.py", "from isocentro.modulos.plano import consulta"),
            ("composicao.py", "from isocentro.modulos import plano"),
        ]
        for lugar, fonte in casos:
            with self.subTest(lugar=lugar, fonte=fonte):
                self.assertEqual(_achados(REGRAS_AD22, [(lugar, fonte)]), [])


class TestAsExcecoesContinuamValendo(unittest.TestCase):
    """Exceção vencida é pior que exceção nenhuma: ninguém questiona o que está
    escrito (a mesma família do "EM ABERTO" já resolvido no ``NOTAS.md``)."""

    def _confere(self, regras, excecoes):
        achados = _achados(regras, _do_pacote())
        for chave, exc in excecoes.items():
            with self.subTest(excecao=chave):
                self.assertTrue(any(_casa(a, chave) for a in achados),
                                f"{chave} já não acontece — tire da lista")
                self.assertRegex(exc.desde, r"^\d{2}/\d{2}/\d{4}$")
                self.assertTrue(exc.saida.strip() and exc.motivo.strip())

    def test_toda_excecao_do_ad22_ainda_acontece(self):
        self._confere(REGRAS_AD22, EXCECOES)

    def test_sao_as_da_espinha(self):
        """A espinha contou quatro arquivos (``qualidade_metodo``,
        ``gatilho_relogio``, ``gatilho``, ``capa_dados``); a R-21 tirou o
        ``gatilho_relogio``. Um arquivo a mais é decisão nova, e decisão nova
        se escreve na espinha também — este número obriga a passar por lá."""
        self.assertEqual(len({arq for arq, _pre in EXCECOES}), 3)

    def test_a_excecao_e_tao_estreita_quanto_o_motivo(self):
        """A do ``capa_dados`` libera o ``interface.simulacao`` (nomes de
        arquivo do cadastro); uma tela de verdade no mesmo arquivo reprova."""
        fonte = ("def f():\n    from isocentro.interface import simulacao\n"
                 "def g():\n    from isocentro.interface import gui\n")
        novos = _fora_das_excecoes(
            _achados(REGRAS_AD22, [("banco/capa_dados.py", fonte)]), EXCECOES)
        self.assertEqual([a[3] for a in novos], ["isocentro.interface.gui"])

    @unittest.skipUnless(R58_FEITA, "acende com a R-58 (AD-38)")
    def test_toda_excecao_do_ad38_ainda_acontece(self):
        self._confere(REGRAS_AD38, EXCECOES_RT)


class TestCamadaRt(unittest.TestCase):
    """AD-38. Desligada até a R-58 terminar: o ``dicom/`` de hoje ainda é a
    leitura, o modelo e o desenho juntos."""

    @unittest.skipUnless(R58_FEITA, "acende com a R-58 (AD-38)")
    def test_rt_puro_e_ninguem_de_baixo_o_importa(self):
        novos = _fora_das_excecoes(_achados(REGRAS_AD38, _do_pacote()), EXCECOES_RT)
        self.assertEqual(novos, [], "dependência proibida:\n  " + _relatorio(novos))

    def test_as_regras_mordem(self):
        """Roda com a regra desligada, de propósito: é o que garante que o dia
        de acender não começa por consertar o teste."""
        casos = [
            ("rt/x.py", "from isocentro.dados import equipe"),
            ("rt/x.py", "from PIL import Image"),
            ("rt/x.py", "import matplotlib.pyplot as plt"),
            ("rt/x.py", "import zipfile"),
            ("rt/x.py", "from pathlib import Path"),
            ("rt/x.py", "import socket"),
            ("rt/x.py", "import pyodbc"),
            ("rt/x.py", "from functools import lru_cache"),
            ("rt/x.py", "import threading"),
            ("rt/x.py", "def f(c):\n    return open(c).read()"),
            ("rt/x.py", "from PyQt5.QtCore import Qt"),
            # A lista é PERMITIDA: o que ninguém lembrou de proibir também cai.
            ("rt/x.py", "import subprocess"),
            ("rt/x.py", "import codecs"),
            ("rt/x.py", "from io import BytesIO"),
            ("rt/x.py", "from concurrent.futures import ThreadPoolExecutor"),
            ("rt/x.py", "from functools import cached_property"),
            ("rt/x.py", "import scipy.ndimage"),
            ("adaptadores/dicom/x.py", "from isocentro.rt import margem"),
            ("banco/x.py", "from isocentro.dicom import dicom_rt"),
            ("nucleo/x.py", "from isocentro.rt import margem"),
            ("papel/x.py", "from isocentro.banco import capa_dados"),
        ]
        for lugar, fonte in casos:
            with self.subTest(lugar=lugar, fonte=fonte):
                self.assertTrue(_achados(REGRAS_AD38, [(lugar, fonte)]))

    def test_o_que_o_rt_pode(self):
        fonte = ("from __future__ import annotations\nimport math\n"
                 "import numpy as np\nimport pydicom\nfrom dataclasses import dataclass\n"
                 "from isocentro.rt import margem\nfrom . import vizinho\n")
        self.assertEqual(_achados(REGRAS_AD38, [("rt/x.py", fonte)]), [])


class TestManifestoEComposicao(unittest.TestCase):
    """AD-40. Desligada até a R-60 criar o tipo ``Manifesto`` e as duas listas
    de composição."""

    @unittest.skipUnless(R60_FEITA, "acende com a R-60 (AD-40)")
    def test_composicao_do_pacote(self):
        problemas = _problemas_da_composicao(*_composicao_do_disco())
        self.assertEqual(problemas, [], "\n  ".join(problemas))

    @unittest.skipUnless(R60_FEITA, "acende com a R-60 (AD-40)")
    def test_a_raiz_de_composicao_so_importa_modulos_e_nucleo(self):
        novos = _achados(REGRAS_AD40, _do_pacote())
        self.assertEqual(novos, [], "dependência proibida:\n  " + _relatorio(novos))

    _TABELA = ("| Módulo | Classe | Justificativa | Decidido em |\n"
               "| --- | --- | --- | --- |\n"
               "| Plano (`modulos/plano`) | C | ... | ... |\n")
    _PLANO = ('MANIFESTO = Manifesto(nome="plano", classe="C",\n'
              '    verificacoes=("plano.segunda_checagem",))\n')
    _COMPOSICAO = "from isocentro.modulos import plano\n"
    _TELAS = "from isocentro.interface.modulos import plano\n"

    def test_um_modulo_certo_passa(self):
        self.assertEqual(_problemas_da_composicao(
            {"plano": self._PLANO}, self._COMPOSICAO, self._TELAS, self._TABELA), [])

    def test_as_regras_mordem(self):
        """Roda com a regra desligada, pelo mesmo motivo do ``rt``. Cada caso
        estraga UMA coisa do módulo certo acima."""
        casos = {
            "fora da lista": ({"plano": self._PLANO}, "", self._TELAS, self._TABELA),
            "sem manifesto": ({"plano": "X = 1\n"}, self._COMPOSICAO, self._TELAS,
                              self._TABELA),
            "sem tela": ({"plano": self._PLANO}, self._COMPOSICAO, "", self._TABELA),
            "tela sem manifesto": ({"plano": self._PLANO}, self._COMPOSICAO,
                                   self._TELAS + "from isocentro.interface.modulos "
                                   "import tratamento\n", self._TABELA),
            "prefixo": ({"plano": self._PLANO.replace("plano.segunda", "qa.segunda")},
                        self._COMPOSICAO, self._TELAS, self._TABELA),
            "nome": ({"plano": self._PLANO.replace('nome="plano"', 'nome="Plano"')},
                     self._COMPOSICAO, self._TELAS, self._TABELA),
            "classe divergente": ({"plano": self._PLANO.replace('"C"', '"B"')},
                                  self._COMPOSICAO, self._TELAS, self._TABELA),
            # Sem linha na tabela, vale C (AD-39): B declarado no manifesto
            # seria a classe rebaixada por quem edita o código.
            "classe sem decisão": ({"plano": self._PLANO.replace('"C"', '"B"')},
                                   self._COMPOSICAO, self._TELAS, ""),
            # Menção de passagem a ``modulos/plano`` na linha de outro módulo
            # não dá ao Plano a classe daquela linha.
            "classe de outra linha": (
                {"plano": self._PLANO.replace('"C"', '"A"')}, self._COMPOSICAO,
                self._TELAS, self._TABELA
                + "| `modulos/indicadores` (lê a fachada de `modulos/plano`) | A | . | . |\n"),
            "classe em conflito": (
                {"plano": self._PLANO}, self._COMPOSICAO, self._TELAS,
                self._TABELA + "| `modulos/plano` | B | . | . |\n"),
            "posicional": ({"plano": 'MANIFESTO = Manifesto("plano", "C")\n'},
                           self._COMPOSICAO, self._TELAS, self._TABELA),
            "anotado sem valor": ({"plano": "MANIFESTO: Manifesto\n"},
                                  self._COMPOSICAO, self._TELAS, self._TABELA),
            "verificacoes em texto": (
                {"plano": self._PLANO.replace('("plano.segunda_checagem",)',
                                              '"plano.segunda_checagem"')},
                self._COMPOSICAO, self._TELAS, self._TABELA),
            # ``modulos/`` vazio com tela listada: toda tela é órfã.
            "tela sem módulo nenhum": ({}, "", self._TELAS, self._TABELA),
        }
        for caso, args in casos.items():
            with self.subTest(caso=caso):
                self.assertTrue(_problemas_da_composicao(*args))

    def test_tela_por_import_relativo_e_vista(self):
        """``from .modulos import plano`` na ``interface/composicao.py`` é a
        tela do Plano, e não ``isocentro.modulos.plano``."""
        self.assertEqual(_problemas_da_composicao(
            {"plano": self._PLANO}, self._COMPOSICAO,
            "from .modulos import plano\n", self._TABELA), [])

    def test_valor_que_nao_e_literal_nao_derruba(self):
        problemas = _problemas_da_composicao(
            {"plano": 'MANIFESTO = Manifesto(nome="plano", classe="C", '
                      'tabelas={["x"]: 1})\n'},
            self._COMPOSICAO, self._TELAS, self._TABELA)
        self.assertEqual(problemas, [])

    def test_descoberta_na_raiz_e_reprovada(self):
        casos = [("composicao.py", "import importlib"),
                 ("composicao.py", "import pkgutil"),
                 ("composicao.py", "from isocentro.dados import ambiente"),
                 ("interface/composicao.py", "import importlib"),
                 ("interface/composicao.py", "import pkgutil")]
        for lugar, fonte in casos:
            with self.subTest(lugar=lugar, fonte=fonte):
                self.assertTrue(_achados(REGRAS_AD40, [(lugar, fonte)]))


if __name__ == "__main__":
    unittest.main()
