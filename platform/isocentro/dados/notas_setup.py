"""Biblioteca das **notas de posicionamento** — os modelos e os do paciente.

O serviço já tem um acervo: umas quarenta notas em ``.docx``, uma por região
("PELVE", "MAMA - RAMPA", "SNC RADIOCIRURGIA"), que o técnico copia e ajusta.
Esse acervo é bom — o vocabulário está estável há anos — e o que faltava era ele
estar **dentro** do programa, onde pode ser escolhido num clique e personalizado
sem virar outro arquivo solto numa pasta.

Aqui cada nota é um registro estruturado: nome, as linhas de acessório e o
preparo (bexiga, reto, gantry, decúbito, braços, jejum) já separados. É a
diferença entre a Capa **adivinhar** o que o texto quer dizer — o que ela faz
hoje com os ``.docx`` antigos, e faz bem, mas é adivinhação — e simplesmente ler.

Na primeira execução a biblioteca é semeada do acervo ``.docx`` que estiver ao
alcance, interpretado pelo :mod:`capa_dados`. Assim ninguém precisa redigitar
quarenta notas para começar a usar.

Só que o acervo ``.docx`` não é empacotado, e o arquivo de trabalho
(``notas_posicionamento.json``) não pode ser — o ``migrar.ps1`` nunca
sobrescreve, e uma cópia dele no zip faria a migração PULAR a biblioteca real do
serviço. O resultado, visto na clínica: instalação nova abria com o seletor de
notas VAZIO, e a única forma de ter notas era migrar de uma instalação antiga.

Daí a semente empacotada, ``assets/notas_modelo.json``: nome diferente do
arquivo de trabalho — então o ``migrar.ps1`` a ignora e ela pode viajar no
pacote — e usada quando não há acervo ``.docx``. Ver ``tools/gerar_notas_modelo.py``.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

from isocentro import raiz
from isocentro.banco import capa_dados
from isocentro.dados import ambiente

# Valor de célula vazia do preparo. Importado por nome para não puxar a
# geração de PDF inteira só por uma constante.
capa_pdf_VAZIO = capa_dados.VAZIO_PREPARO

_LOG = logging.getLogger(__name__)

PASTA_ENV = "ISOCENTRO_NOTAS_DIR"

# Biblioteca em memoria, para quando o arquivo nao puder ser gravado (instalacao
# empacotada em pasta somente-leitura). ``None`` = ainda nao foi preciso.
_cache = None
ARQUIVO = "notas_posicionamento.json"

# A semente empacotada. O nome TEM de ser diferente do ``ARQUIVO`` acima — ver o
# docstring do módulo: é o que a mantém fora da lista do ``migrar.ps1``.
ARQUIVO_SEMENTE = "notas_modelo.json"

# Onde procurar o acervo .docx para semear a biblioteca. Relativo à pasta do
# programa; a primeira que existir é usada.
_ACERVOS = (
    os.path.join("TCs_Teste", "Posicionamento", "NOTAS DE POSICIONAMENTO"),
    "notas_posicionamento",
)


@dataclass
class Nota:
    """Um modelo de posicionamento pronto para aplicar num setup."""
    nome: str = ""
    acessorios: str = ""
    preparo: dict[str, str] = field(default_factory=dict)
    # Modelo do acervo (compartilhado) x nota criada para um paciente. A do
    # paciente aparece no fim da lista e pode ser apagada sem medo.
    modelo: bool = True

    def resumo(self) -> str:
        """Uma linha do que a nota faz, para a lista da tela."""
        linhas = [l for l in self.acessorios.splitlines() if l.strip()]
        prep = [v for k, v in self.preparo.items()
                if v and v != capa_dados.VAZIO_PREPARO]
        return " · ".join(linhas[:3] + prep[:2]) or "(sem conteúdo)"

    def como_setup(self, nome_setup: str = "") -> capa_dados.Setup:
        """Aplica a nota num setup novo (as fotos entram depois)."""
        return capa_dados.Setup(nome=nome_setup or self.nome,
                                acessorios=self.acessorios,
                                preparo=dict(self.preparo))


def _app_dir() -> str:
    # A conta por ``__file__`` valia enquanto o módulo morava na raiz do
    # projeto — ver ``isocentro.raiz.pasta_do_app``.
    return str(raiz.pasta_do_app())


def caminho() -> str:
    base = ambiente.ler(PASTA_ENV) or _app_dir()
    return os.path.join(base, ARQUIVO)


def carregar() -> list[Nota]:
    """A biblioteca: o arquivo do serviço, o acervo ``.docx`` ou a semente."""
    global _cache
    p = caminho()
    # O cache só existe quando a gravação FALHOU: enquanto ele estiver de pé,
    # ele é a verdade, mesmo havendo arquivo em disco — o arquivo é a versão
    # velha, anterior à alteração que não pôde ser gravada, e voltar a ele faria
    # a nota recém-editada sumir da lista no meio do trabalho.
    if _cache is not None:
        return list(_cache)
    if not os.path.exists(p):
        notas = _semear_do_acervo()
        if notas:
            # Sem poder gravar, o cache faz o papel do arquivo: sem um dos dois,
            # toda chamada revarria o acervo ``.docx`` inteiro — e isto roda na
            # thread da interface, a cada aba de posicionamento aberta.
            if not salvar(notas):
                _LOG.warning("Biblioteca de notas nao pode ser gravada em %s — "
                             "as alteracoes valem so nesta sessao", p)
                _cache = list(notas)
            return notas
        # A SEMENTE NÃO É GRAVADA, de propósito. O MIGRAR.txt manda abrir o
        # programa antes de rodar o migrar.ps1 (passo 0, apontar o serviço), e o
        # migrar.ps1 nunca sobrescreve: gravar aqui criaria um
        # ``notas_posicionamento.json`` que faria a migração PULAR a biblioteca
        # real do serviço — e ninguém perceberia, porque as notas da semente são
        # plausíveis. Ela é barata de reler (um JSON pequeno, ao contrário do
        # acervo .docx) e vira arquivo no primeiro ``guardar``, quando passa a
        # haver conteúdo local que merece ser gravado.
        return ler_semente()
    try:
        with open(p, encoding="utf-8") as fh:
            corpo = json.load(fh)
    except (OSError, ValueError):
        _LOG.exception("Biblioteca de notas ilegível em %s", p)
        return []
    return [Nota(nome=n.get("nome", ""), acessorios=n.get("acessorios", ""),
                 preparo=dict(n.get("preparo") or {}),
                 modelo=bool(n.get("modelo", True)))
            for n in (corpo.get("notas") or ())]


def salvar(notas: list[Nota]) -> bool:
    """Grava a biblioteca. Devolve se conseguiu — ver o cache em ``carregar``."""
    p = caminho()
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"versao": 1, "notas": [asdict(n) for n in notas]},
                      fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        return True
    except OSError:
        _LOG.exception("Falha ao gravar a biblioteca de notas em %s", p)
        return False


def guardar(nota: Nota) -> bool:
    """Grava a nota, substituindo a de mesmo nome. Nome vazio não entra.

    Devolve se a biblioteca chegou ao DISCO. Instalação em pasta somente-leitura
    guarda em memória e devolve ``False``: a nota vale nesta sessão, e a tela
    precisa dizer isso — anunciar "guardada na biblioteca" para algo que some no
    fechamento é pior do que não guardar.
    """
    if not nota.nome.strip():
        return False
    alvo = capa_dados.normalizar_nome(nota.nome)
    notas = [n for n in carregar()
             if capa_dados.normalizar_nome(n.nome) != alvo]
    notas.append(nota)
    return _persistir(sorted(notas, key=lambda n: (not n.modelo,
                                                   n.nome.upper())))


def remover(nome: str) -> bool:
    """Tira a nota da biblioteca. Ver ``guardar`` sobre o retorno."""
    alvo = capa_dados.normalizar_nome(nome)
    return _persistir([n for n in carregar()
                       if capa_dados.normalizar_nome(n.nome) != alvo])


def _persistir(notas: list[Nota]) -> bool:
    """Grava no disco e mantém o cache alinhado com o que a tela mostra.

    Sem atualizar o cache, uma alteração feita com o disco indisponível era
    perdida na chamada seguinte a ``carregar`` — a nota sumia da lista no meio
    do trabalho, sem nada dizendo por quê.
    """
    global _cache
    if salvar(notas):
        _cache = None
        return True
    _cache = list(notas)
    return False


def por_nome(nome: str) -> Optional[Nota]:
    alvo = capa_dados.normalizar_nome(nome)
    return next((n for n in carregar()
                 if capa_dados.normalizar_nome(n.nome) == alvo), None)


# ── Semente a partir do acervo .docx ─────────────────────────────────────────

def pasta_do_acervo() -> str:
    """A primeira pasta de acervo ``.docx`` que existir, ou ""."""
    base = _app_dir()
    for rel in _ACERVOS:
        p = os.path.join(base, rel)
        if os.path.isdir(p):
            return p
    return ""


def _assinatura(nota: Nota) -> tuple:
    """O que a nota MANDA FAZER, sem depender de grafia.

    Duas notas com esta mesma assinatura dizem a mesma coisa; com nomes
    diferentes, continuam sendo notas diferentes — ``PRÓSTATA`` e ``COLO DE
    ÚTERO`` usam a mesma montagem, e fundi-las deixaria quem procura pela região
    sem encontrar nada.
    """
    acess = " ".join(nota.acessorios.split()).upper()
    prep = tuple(sorted((k, (v or "").strip().upper())
                        for k, v in nota.preparo.items()
                        if v and v.strip().upper() not in ("", capa_pdf_VAZIO)))
    return (acess, prep)


def deduplicar(notas: list[Nota]) -> list[Nota]:
    """Tira só as notas VERDADEIRAMENTE repetidas: mesmo nome e mesmo conteúdo.

    Nome igual com conteúdo diferente é variante (a CT-RA deita o paciente de
    outro jeito) e fica, desambiguada por quem semeia. Conteúdo igual com nome
    diferente é região diferente que por acaso usa os mesmos acessórios — some
    da lista quem procura pelo nome da região.
    """
    vistos: set[tuple] = set()
    limpas: list[Nota] = []
    for n in notas:
        chave = (capa_dados.normalizar_nome(n.nome), _assinatura(n))
        if chave in vistos:
            continue
        vistos.add(chave)
        limpas.append(n)
    return limpas


def caminho_da_semente() -> str:
    """A semente empacotada — em ``assets/``, como os logos.

    Não é ``_app_dir()``, e a diferença é a razão de ``raiz`` ter DUAS funções:
    no pacote do PyInstaller o executável fica um nível ACIMA de onde os
    ``datas`` são desdobrados (``_internal/assets``). ``pasta_do_app`` devolve
    a do executável, ``pasta_assets`` a dos recursos — trocar uma pela outra
    aqui dá o seletor de notas VAZIO na instalação nova, que é o erro nº 6 do
    ``gerar_executavel`` e durou meses.
    """
    return str(raiz.pasta_assets() / ARQUIVO_SEMENTE)


def ler_semente() -> list[Nota]:
    """Os modelos que vieram no pacote. Lista vazia se não houver semente.

    Semente ilegível não derruba o app nem esvazia a biblioteca: quem abre a
    aba de posicionamento quer trabalhar, e um traceback aqui custaria o
    posicionamento inteiro por causa de um arquivo de apoio.
    """
    p = caminho_da_semente()
    if not os.path.exists(p):
        _LOG.info("Sem semente de notas em %s", p)
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            corpo = json.load(fh)
    except (OSError, ValueError):
        _LOG.exception("Semente de notas ilegível em %s", p)
        return []
    notas = [Nota(nome=n.get("nome", ""), acessorios=n.get("acessorios", ""),
                  preparo=dict(n.get("preparo") or {}), modelo=True)
             for n in (corpo.get("notas") or ())
             if capa_dados.normalizar_nome(n.get("nome", ""))]
    _LOG.info("Biblioteca de notas semeada com %d modelos de %s", len(notas), p)
    return sorted(notas, key=lambda n: n.nome.upper())


def semear() -> list[Nota]:
    """Os modelos iniciais: o acervo ``.docx`` se houver, senão a semente.

    O acervo ganha quando existe. Quem larga os ``.docx`` na pasta do programa
    está dizendo "use estes"; ignorá-los em favor de uma lista congelada dentro
    do pacote seria o app teimando contra o serviço.
    """
    return _semear_do_acervo() or ler_semente()


def _semear_do_acervo() -> list[Nota]:
    """Lê o acervo ``.docx`` e devolve as notas interpretadas.

    Varre também as subpastas — o acervo do serviço tem uma para a CT-RA, e as
    notas de lá têm o MESMO nome com conteúdo diferente (a de tórax pede braços
    elevados e outra altura de rampa). Ficar com "a primeira encontrada" jogava
    fora quatro montagens legítimas em silêncio, e quem procurasse a da CT-RA
    encontrava a errada com o nome certo. Aqui a subpasta entra no nome; só
    quando nome E conteúdo coincidem é que há repetição de verdade.
    """
    pasta = pasta_do_acervo()
    if not pasta:
        _LOG.info("Nenhum acervo de notas .docx encontrado para semear")
        return []
    achadas: list[tuple[str, Nota]] = []      # (origem, nota)
    for raiz_, _dirs, arquivos in os.walk(pasta):
        origem = os.path.relpath(raiz_, pasta).strip(os.sep + "./ ")
        if origem == ".":
            origem = ""
        for arq in sorted(arquivos):
            if not arq.lower().endswith(capa_dados.EXT_NOTAS):
                continue
            nome = os.path.splitext(arq)[0].strip()
            if not capa_dados.normalizar_nome(nome):
                continue
            acessorios, preparo = capa_dados.interpretar_notas(
                capa_dados.ler_nota(os.path.join(raiz_, arq)))
            if not acessorios and not preparo:
                continue
            achadas.append((origem, Nota(nome=nome, acessorios=acessorios,
                                         preparo=preparo, modelo=True)))

    # Só os nomes que colidem ganham a origem no rótulo. Carimbar a subpasta em
    # todas encheria a lista de "(DUO)" onde não há ambiguidade nenhuma — e o
    # que se procura aqui é a região, não de que pasta a nota veio.
    contagem: dict[str, int] = {}
    for _org, n in achadas:
        chave = capa_dados.normalizar_nome(n.nome)
        contagem[chave] = contagem.get(chave, 0) + 1
    notas = []
    for origem, n in achadas:
        if origem and contagem[capa_dados.normalizar_nome(n.nome)] > 1:
            n.nome = f"{n.nome} ({origem.replace(os.sep, ' · ')})"
        notas.append(n)
    notas = deduplicar(notas)
    _LOG.info("Biblioteca de notas semeada com %d modelos de %s",
              len(notas), pasta)
    return sorted(notas, key=lambda n: n.nome.upper())
