"""Cadastro da **simulação**: o que o dosimetrista registra ao sair da TC.

É o primeiro elo da corrente. O dosimetrista posiciona o paciente na tomografia,
fotografa o setup, anota como montou e guarda o imobilizador. Até agora isso
vivia em fotos no celular e num ``.docx`` solto numa pasta qualquer — e a Capa,
lá no fim, tinha de adivinhar o que cada arquivo significava.

Aqui o registro nasce **estruturado**, na pasta padronizada::

    <raiz>/NOME_DO_PACIENTE_1234567ABC/mm-aaaa/
        SIMULACAO.json          o cadastro inteiro, legível por programa
        POSICIONAMENTO.txt      a mesma coisa em texto, legível por pessoa
        01_TORAX_1.jpg          fotos, já no tamanho em que serão impressas
        01_TORAX_2.jpg
        02_FEMUR_1.jpg

Por que **pasta aberta e não um pacote**: quem abre essa pasta no explorador
precisa ver as fotos — o técnico confere o setup nelas antes de deitar o
paciente. Um ``.zip`` esconderia exatamente o que mais se olha. E por que
**JSON + txt**: o JSON é o que a Capa lê sem interpretar nada (fim da
adivinhação de vocabulário); o txt é o que sobra de útil se um dia não houver
programa nenhum para abrir o JSON.

As fotos são gravadas já reamostradas para a resolução de impressão. O original
de 5 MB do celular não serve para nada depois — a capa imprime num quadro de
quatro polegadas — e guardá-lo encheria o compartilhamento sem devolver nada.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from isocentro.banco import capa_dados
from isocentro.dados import ambiente

_LOG = logging.getLogger(__name__)

# ── Onde as simulações são gravadas ──────────────────────────────────────────
# Mesma convenção do resto do app: variável de ambiente, escolha guardada pelo
# admin, e um padrão que funciona sem ninguém configurar nada.
PASTA_ENV = "ISOCENTRO_SIMULACOES"

ARQ_CADASTRO = "SIMULACAO.json"
ARQ_NOTA = "POSICIONAMENTO.txt"

# Resolução em que as fotos são gravadas — a mesma da impressão da capa. Ver o
# comentário do módulo.
_DPI = 200
_LADO_MAX = 1400            # px no maior lado; ~4 pol a 200 dpi com folga

_pasta_escolhida = ""


def definir_raiz(caminho: str) -> None:
    """Aponta onde as simulações são gravadas. "" volta ao padrão."""
    global _pasta_escolhida
    _pasta_escolhida = str(caminho or "").strip()
    # O índice é de UMA raiz. Ele já guarda qual, e o ``_varredura`` compara —
    # mas esquecer aqui é o que garante que a raiz nova seja lida na hora, em
    # vez de esperar o minuto de uma varredura que nem é dela.
    esquecer_indice()


def raiz() -> str:
    """Pasta-mãe das simulações.

    Sem configuração, **Documentos** do usuário: é onde alguém sem permissão de
    rede consegue gravar hoje, e é achável sem instrução. O admin aponta o
    compartilhamento quando houver um.
    """
    if _pasta_escolhida:
        return _pasta_escolhida
    env = ambiente.ler(PASTA_ENV)
    if env:
        return env
    # A escolha do admin vale para o SERVIÇO, não para a estação em que foi
    # feita — ver :mod:`config_servico`.
    try:
        from isocentro.dados import config_servico
        do_servico = config_servico.valor(config_servico.RAIZ_SIMULACOES)
    except Exception:  # noqa: BLE001
        do_servico = ""
    if do_servico:
        return do_servico
    return os.path.join(os.path.expanduser("~"), "Documents", "Simulacoes")


# ── Modelo ───────────────────────────────────────────────────────────────────

@dataclass
class Simulacao:
    """Uma sessão de tomografia registrada: paciente, setups e imobilizadores."""
    nome: str = ""
    registro: str = ""
    nascimento: str = ""
    setups: list[capa_dados.Setup] = field(default_factory=list)
    # Imobilizadores individuais retirados do inventário (ver ``inventario.py``).
    imobilizadores: list[dict] = field(default_factory=list)
    observacoes: str = ""
    cadastrada_em: str = ""
    cadastrada_por: str = ""

    def valida(self) -> list[str]:
        """O que impede o cadastro. Lista vazia = pode gravar.

        Só o indispensável: sem nome não há pasta, e sem foto nenhuma o cadastro
        não registra a única coisa que só a simulação produz. O resto — nota,
        acessório, preparo — pode ser completado depois, e travar por causa
        disso deixaria o dosimetrista esperando no corredor.
        """
        faltas = []
        if not self.nome.strip():
            faltas.append("Escolha o paciente.")
        if not any(s.fotos for s in self.setups):
            faltas.append("Arraste ao menos uma foto de posicionamento.")
        return faltas


# ── Nomes de arquivo e de pasta ──────────────────────────────────────────────

def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def slug(texto: str, limite: int = 60) -> str:
    """Forma segura para nome de arquivo/pasta no Windows."""
    s = _sem_acento(str(texto or "")).upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
    return s[:limite] or "SEM_NOME"


def _gaveta(parte: str) -> str:
    """A pasta de UMA LETRA onde o paciente mora: ``ANTONIO_...`` → ``A``.

    Com centenas de pacientes, a raiz virava uma lista única impossível de
    percorrer no Explorer — quem procura à mão abre a letra e acha.

    O ``slug`` já entregou o nome sem acento, em maiúsculas e só com A-Z0-9,
    então a inicial é sempre uma dessas. Nome que comece por dígito (não
    deveria acontecer com gente, mas o campo aceita) cai em ``#``, para não
    criar gaveta numerada nem deixar o paciente fora de gaveta nenhuma.
    """
    inicial = (parte or "")[:1]
    return inicial if inicial.isalpha() else "#"


def pasta_do_paciente(nome: str, registro: str = "") -> str:
    """``<raiz>/A/NOME_DO_PACIENTE_1234567ABC`` (ver ``slug`` e ``_gaveta``).

    O registro entra no nome da pasta porque homônimo existe — e uma pasta
    trocada aqui contamina tudo que vem depois.

    A GAVETA da inicial é nova. Cadastro antigo está direto na raiz, sem ela, e
    continua lá: nada foi movido, porque mover pasta de paciente é mexer em
    dado clínico. Quem LÊ tem de olhar os dois layouts — ver
    ``_pastas_de_paciente`` e ``historico``. Esta função devolve só o lugar
    NOVO, que é onde se grava daqui em diante.
    """
    parte = slug(nome)
    if registro.strip():
        parte = f"{parte}_{slug(registro, 20)}"
    return os.path.join(raiz(), _gaveta(parte), parte)


def pasta_da_data(quando: Optional[date] = None) -> str:
    """``mm-aaaa`` — o mês da simulação.

    Com hífen, não barra: a barra é separador de caminho. Um paciente
    replanejado no mesmo mês reaproveita a pasta, que é o que se quer — o
    replanejamento é a mesma simulação revisada, não outra.
    """
    d = quando or date.today()
    return f"{d.month:02d}-{d.year}"


# ── Gravação ─────────────────────────────────────────────────────────────────

def cadastrar(sim: Simulacao, quando: Optional[date] = None) -> str:
    """Grava a simulação e devolve a pasta criada. Levanta em caso de falha.

    Não apaga o que já está lá: cadastrar de novo no mesmo mês **substitui os
    arquivos daquele cadastro** e mantém o resto. Assim uma segunda leva de
    fotos não obriga a refazer tudo, e nada que alguém pôs à mão na pasta se
    perde.
    """
    faltas = sim.valida()
    if faltas:
        raise ValueError(" ".join(faltas))

    destino = os.path.join(pasta_do_paciente(sim.nome, sim.registro),
                           pasta_da_data(quando))
    os.makedirs(destino, exist_ok=True)

    sim.cadastrada_em = (quando or date.today()).strftime("%d/%m/%Y")
    arquivos = _gravar_fotos(sim, destino)
    _gravar_json(sim, destino, arquivos)
    _gravar_txt(sim, destino)
    _LOG.info("Simulação de %s cadastrada em %s", sim.nome, destino)
    # O índice acabou de ficar velho por causa DESTA gravação, e quem cadastrou
    # vai procurar a pasta em seguida — é o passo seguinte da corrente (a Capa
    # abre o posicionamento que acabou de ser registrado). Esperar o minuto
    # aqui seria o programa não achar o que ele mesmo escreveu.
    esquecer_indice()
    return destino


def _gravar_fotos(sim: Simulacao, destino: str) -> list[list[str]]:
    """Escreve as fotos e devolve, por setup, os nomes de arquivo gravados."""
    # Fotos de um cadastro anterior do mesmo mês saem: se ficassem, a Capa
    # acharia fotos de duas levas e não saberia quais são as atuais.
    for antigo in os.listdir(destino):
        if re.match(r"^\d{2}_.*\.(jpg|jpeg|png)$", antigo, re.IGNORECASE):
            _remover(os.path.join(destino, antigo))

    por_setup: list[list[str]] = []
    for i, s in enumerate(sim.setups, start=1):
        nomes = []
        for j, dados in enumerate([f for f in s.fotos if f], start=1):
            nome = f"{i:02d}_{slug(s.nome or f'SETUP{i}', 24)}_{j}.jpg"
            try:
                with open(os.path.join(destino, nome), "wb") as fh:
                    fh.write(_para_impressao(dados))
                nomes.append(nome)
            except OSError:
                _LOG.exception("Falha ao gravar a foto %s", nome)
        por_setup.append(nomes)
    return por_setup


def _para_impressao(dados: bytes) -> bytes:
    """Reduz a foto ao tamanho em que será impressa, em JPEG.

    Falha aqui devolve o original: pior caso o arquivo fica grande, que é o
    comportamento de antes — e não perder a foto é o que importa.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(dados))
        maior = max(img.width, img.height)
        if maior > _LADO_MAX:
            escala = _LADO_MAX / maior
            img = img.resize((max(int(img.width * escala), 1),
                              max(int(img.height * escala), 1)), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True,
                                dpi=(_DPI, _DPI))
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        _LOG.exception("Falha ao reamostrar foto da simulação — grava o original")
        return dados


def _gravar_json(sim: Simulacao, destino: str, arquivos: list[list[str]]) -> None:
    """O cadastro legível por programa — é daqui que a Capa lê."""
    corpo = {
        "versao": 1,
        "paciente": {"nome": sim.nome, "registro": sim.registro,
                     "nascimento": sim.nascimento},
        "cadastrada_em": sim.cadastrada_em,
        "cadastrada_por": sim.cadastrada_por,
        "observacoes": sim.observacoes,
        "imobilizadores": sim.imobilizadores,
        "setups": [
            {"nome": s.nome, "acessorios": s.acessorios, "preparo": s.preparo,
             "fotos": arquivos[i] if i < len(arquivos) else []}
            for i, s in enumerate(sim.setups)
        ],
    }
    _escrever(os.path.join(destino, ARQ_CADASTRO),
              json.dumps(corpo, ensure_ascii=False, indent=2))


def _gravar_txt(sim: Simulacao, destino: str) -> None:
    """A mesma nota em texto — para quem abre a pasta e não roda o programa.

    A montagem vem primeiro e sai corrida, uma instrução por linha: é ela que
    se lê com o paciente já deitado na mesa, e linha em branco entre acessório
    e preparo partiria em dois o que é uma coisa só — por isso o preparo também
    deixou de sair espremido numa linha com "·". O carimbo da simulação (nome,
    registro, quando e por quem) é rodapé: identifica a folha, não posiciona
    ninguém, e é dele que a única linha em branco separa a montagem.
    """
    linhas: list[str] = []
    for i, s in enumerate(sim.setups, start=1):
        if linhas:
            linhas.append("")
        linhas.append(f"[{i}] {s.nome or f'SETUP {i}'}")
        linhas.extend(l for l in s.acessorios.splitlines() if l.strip())
        linhas.extend(f"{k}: {v}" for k, v in s.preparo.items()
                      if v and v != capa_dados.VAZIO_PREPARO)
    if sim.imobilizadores:
        if linhas:
            linhas.append("")
        linhas.append("IMOBILIZADORES")
        for m in sim.imobilizadores:
            linhas.append(f"{m.get('codigo', '?')} — {m.get('tipo', '')}")
    if sim.observacoes.strip():
        if linhas:
            linhas.append("")
        linhas.append("OBSERVAÇÕES")
        linhas.append(sim.observacoes.strip())
    if linhas:
        linhas.append("")
    linhas.append(f"SIMULAÇÃO — {sim.nome}")
    if sim.registro:
        linhas.append(f"Registro: {sim.registro}")
    if sim.cadastrada_em:
        linhas.append(f"Simulada em: {sim.cadastrada_em}"
                      + (f" por {sim.cadastrada_por}" if sim.cadastrada_por else ""))
    _escrever(os.path.join(destino, ARQ_NOTA), "\n".join(linhas) + "\n")


def _escrever(caminho: str, texto: str) -> None:
    """Escrita atômica — nunca deixa um arquivo meio gravado na pasta."""
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(texto)
    os.replace(tmp, caminho)


def _remover(caminho: str) -> None:
    try:
        os.remove(caminho)
    except OSError:
        pass


# ── Leitura: é assim que a Capa reencontra a simulação ───────────────────────

def carregar(pasta: str) -> Optional[Simulacao]:
    """Lê o ``SIMULACAO.json`` de uma pasta de simulação. ``None`` se não houver."""
    caminho = os.path.join(pasta, ARQ_CADASTRO)
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            corpo = json.load(fh)
    except (OSError, ValueError):
        _LOG.exception("Cadastro de simulação ilegível em %s", pasta)
        return None

    pac = corpo.get("paciente") or {}
    sim = Simulacao(nome=pac.get("nome", ""), registro=pac.get("registro", ""),
                    nascimento=pac.get("nascimento", ""),
                    observacoes=corpo.get("observacoes", ""),
                    imobilizadores=list(corpo.get("imobilizadores") or ()),
                    cadastrada_em=corpo.get("cadastrada_em", ""),
                    cadastrada_por=corpo.get("cadastrada_por", ""))
    for s in corpo.get("setups") or ():
        fotos = []
        for nome in s.get("fotos") or ():
            try:
                with open(os.path.join(pasta, nome), "rb") as fh:
                    fotos.append(fh.read())
            except OSError:
                _LOG.info("Foto %s citada no cadastro não está na pasta", nome)
        sim.setups.append(capa_dados.Setup(
            nome=s.get("nome", ""), acessorios=s.get("acessorios", ""),
            preparo=dict(s.get("preparo") or {}), fotos=fotos,
            arquivo=ARQ_CADASTRO))
    return sim


# Intervalo MÍNIMO entre duas varreduras — não é prazo de validade.
#
# A diferença decide o comportamento, e ela veio de uma medição: com 400
# pacientes em disco LOCAL, uma varredura custa 3,8 s (a raiz da clínica é de
# REDE, então isso é piso). Um prazo de validade faria a tela congelar esses
# segundos a cada minuto de uso — trocar um problema por outro.
#
# A regra é outra: o índice vale enquanto ACHA. Quando a busca não acha, e só
# então, ele é refeito uma vez e a busca é repetida. É exatamente o caso em que
# o dado velho importaria — o cadastro que outra estação acabou de gravar —, e
# é o momento em que pagar a varredura tem retorno, porque a alternativa é
# dizer "este paciente não tem pasta".
#
# O intervalo existe só para o paciente que REALMENTE não tem cadastro não
# refazer a varredura a cada tecla: nesse caso ela falharia de novo, e uma vez
# por minuto basta para não travar a navegação.
SEGUNDOS_ENTRE_VARREDURAS = 60.0

# A varredura guardada: raiz, quando foi feita, e as linhas cruas.
_indice: dict = {"raiz": None, "em": 0.0, "linhas": None, "pais": None}


def esquecer_indice() -> None:
    """Joga fora a varredura guardada. Chamado quando o disco muda por AQUI."""
    _indice["linhas"] = None


def _varredura(base: str, forcar: bool = False) -> list:
    """``(registro, nome, pasta_do_mês, hora_da_pasta_do_paciente)`` de cada
    cadastro sob ``base``.

    **Guarda a VARREDURA, não a decisão** — e essa distinção é o ponto. A regra
    de casamento (registro quando os dois lados têm um, senão nome; o mês mais
    recente) mora no :func:`_casar`, num lugar só. Um índice já resolvido seria
    uma segunda versão dessa regra, e as duas divergiriam no primeiro conserto
    feito só num dos lados.

    **O que ele economiza é E/S, e é ela que dói**: a varredura abre uma
    listagem de diretório por paciente e faz o parse de um JSON por pasta de
    mês. Numa raiz de rede que cresce — e ela cresce, um paciente por
    tomografia — isso vira centenas de idas ao compartilhamento **a cada
    montagem de capa**, e a capa é montada ao navegar na busca. Pedido em
    08/09/2026, com o crescimento das pastas como razão.

    Normalizar fica de fora daqui de propósito: é decisão de quem compara, e
    normalizar N linhas em memória não custa nada perto de uma leitura de rede.
    """
    agora = time.monotonic()
    if _indice["linhas"] is not None and _indice["raiz"] == base and not forcar:
        return _indice["linhas"]
    erros: list = []
    pais: dict = {}
    linhas = []
    for pasta_pac in _pastas_de_paciente(base, erros, pais):
        # A hora da PASTA DO PACIENTE, guardada junto. É ela que permite
        # revalidar um achado com UM ``stat``, em vez de varrer tudo de novo:
        # acrescentar uma pasta de mês (um replanejamento, ou o cadastro que
        # outra estação gravou) muda a hora do pai. Ver ``_ainda_vale``.
        marca = _marca_de(pasta_pac)
        for mes in _subpastas(pasta_pac, erros):
            dados = _identificacao(mes)
            if dados is None:
                continue
            linhas.append((dados[0], dados[1], mes, marca))
    if erros:
        # Varredura pela metade NÃO é guardada. Antes do índice, uma piscada do
        # compartilhamento se curava na navegação seguinte; guardada, ela faria
        # toda busca responder "sem cadastro" até a próxima varredura — em
        # silêncio, que é o modo de falhar que este projeto não aceita.
        _LOG.info("Varredura incompleta (%s pasta[s] ilegível[eis]) — não "
                  "guardada", len(erros))
        return linhas
    _indice.update(raiz=base, em=agora, linhas=linhas, pais=pais)
    return linhas


def procurar(nome: str, registro: str = "") -> str:
    """A pasta de simulação MAIS RECENTE do paciente, ou "".

    A Capa chama isto para achar o que o dosimetrista registrou na TC — é o que
    liga as duas pontas da corrente. Casa pelo registro quando há um (homônimo
    existe) e pelo nome quando não.

    A leitura do disco passa pelo :func:`_varredura`, que a guarda. Quando a
    busca NÃO acha, o índice é refeito uma vez e a busca repetida — ver
    ``SEGUNDOS_ENTRE_VARREDURAS``.
    """
    base = raiz()
    if not os.path.isdir(base):
        return ""
    alvo_reg = capa_dados.normalizar_id(registro)
    alvo_nome = capa_dados.normalizar_nome(nome)
    if not alvo_reg and not alvo_nome:
        return ""

    linha = _casar(alvo_reg, alvo_nome, _varredura(base))
    if linha is not None and _ainda_vale(linha):
        return linha[2]
    # Duas razões para chegar aqui, e elas pedem coisas diferentes:
    #
    # * NÃO ACHOU. Pode ser cadastro novo, de outra estação. Vale reler, mas só
    #   respeitando o intervalo: o paciente que realmente não tem pasta falharia
    #   de novo, e varrer tudo a cada tecla é o que se está evitando;
    # * ACHOU e a pasta MUDOU. Aqui há prova de que o disco andou — a hora do
    #   pai mudou ou a pasta sumiu —, e reler é obrigatório, sem intervalo
    #   nenhum. Foi o defeito achado na revisão de 08/09/2026: com o índice
    #   quente, uma simulação nova cadastrada noutra estação ficava invisível
    #   pelo resto da sessão, e a Capa montava o posicionamento ANTIGO. Num
    #   replanejamento isso é a folha errada indo para a sala.
    if linha is None and not _vale_reler():
        return ""
    linha = _casar(alvo_reg, alvo_nome, _varredura(base, forcar=True))
    return linha[2] if linha is not None else ""


def _ainda_vale(linha: tuple) -> bool:
    """O achado guardado ainda corresponde ao disco?

    Alguns ``stat``, e é o que substitui uma varredura inteira: a pasta do mês
    ainda existe, a hora da pasta do PACIENTE é a mesma de quando foi lida, e o
    mesmo vale para a raiz e as gavetas. As duas últimas partes são o que
    enxerga a pasta NOVA — acrescentá-la muda a hora do pai —, e é assim que um
    replanejamento aparece sem custo.
    """
    _reg, _nom, mes, marca = linha
    if not os.path.isdir(mes) or _marca_de(os.path.dirname(mes)) != marca:
        return False
    # E os diretórios onde uma pasta de PACIENTE nova aparece: a raiz e as
    # gavetas. Sem eles, o cadastro que outra estação gravou NOUTRO paciente
    # ficava invisível pelo resto da sessão — o mesmo defeito de 08/09/2026
    # entrando pela porta do lado, e ele acontece de verdade: o mesmo paciente
    # recadastrado COM registro ganha pasta nova (o nome dela leva o registro),
    # e a antiga não muda de hora.
    #
    # São ``1 + gavetas`` ``stat`` — dezenas, contra centenas de aberturas de
    # arquivo de uma varredura.
    return all(_marca_de(pai) == quando
               for pai, quando in (_indice["pais"] or {}).items())


def _vale_reler() -> bool:
    """Já passou o intervalo mínimo desde a última varredura?

    Sem isto, o paciente que REALMENTE não tem cadastro refaria a varredura a
    cada busca — e a busca acontece ao navegar. Ele falharia de novo, ao preço
    de segundos por tecla.
    """
    return (time.monotonic() - _indice["em"]) >= SEGUNDOS_ENTRE_VARREDURAS


def _casar(alvo_reg: str, alvo_nome: str, linhas: list):
    """A REGRA, num lugar só: qual LINHA é a deste paciente (ou ``None``).

    Separada do :func:`procurar` porque ele a aplica duas vezes — antes e
    depois da releitura. Duplicá-la ali daria duas cópias da mesma decisão no
    mesmo método, que é como elas começam a divergir.

    Devolve a linha inteira, e não só o caminho, porque quem chama precisa da
    marca de hora para revalidar (ver :func:`_ainda_vale`).
    """
    candidatas = []
    for reg, nom, mes, marca in linhas:
        # Registro casa quando os DOIS lados têm um; senão vale o nome. O
        # cadastro feito sem registro (paciente que ainda não está no
        # relatório) ficava invisível para toda busca que trouxesse um.
        if alvo_reg and capa_dados.normalizar_id(reg):
            bate = capa_dados.normalizar_id(reg) == alvo_reg
        else:
            bate = bool(alvo_nome) and capa_dados.normalizar_nome(nom) == alvo_nome
        if bate:
            candidatas.append((_ordem_mes(os.path.basename(mes)),
                               (reg, nom, mes, marca)))
    if not candidatas:
        return None
    # Desempate pelo CAMINHO, como era antes do índice. O ``max`` original
    # comparava a tupla ``(ordem, caminho)`` inteira; ordenar só pela ordem
    # devolveria o primeiro máximo, na ordem do ``scandir`` — e com duas pastas
    # do MESMO mês (o cadastro sem registro e o recadastro com registro) a
    # escolha invertia calada. Achado na revisão de 08/09/2026.
    return max(candidatas, key=lambda c: (c[0], c[1][2]))[1]


def _e_gaveta(nome: str) -> bool:
    """A pasta é uma gaveta de inicial, e não um paciente?

    Um caractere só. Slug de paciente nunca tem um: ou traz o nome inteiro, ou
    o nome mais o registro. É por isso que dá para distinguir os dois layouts
    olhando o nome, sem marcar nada em disco.
    """
    return len(nome) == 1 and (nome.isalpha() or nome == "#")


def _marca_de(caminho: str) -> float:
    """A hora da pasta, ou 0.0 se ela não puder ser lida.

    É a moeda da revalidação barata: acrescentar uma pasta DENTRO desta muda
    esta hora, e conferi-la custa um ``stat`` em vez de uma varredura.
    """
    try:
        return os.stat(caminho).st_mtime
    except OSError:
        return 0.0


def _pastas_de_paciente(base: str, erros: Optional[list] = None,
                        pais: Optional[dict] = None) -> list[str]:
    """Pastas de paciente nos DOIS layouts, para a busca não perder ninguém.

    Depois da gaveta, o caminho é ``<raiz>/A/PACIENTE``; antes dela era
    ``<raiz>/PACIENTE``, e essas pastas continuam onde estão. Se a varredura
    descesse só até a gaveta, todo paciente cadastrado ANTES sumiria da busca —
    e a Capa responderia "esse paciente não tem simulação" para quem tem.

    ``pais`` recebe a hora da raiz e de cada gaveta — os diretórios onde uma
    pasta de PACIENTE nova aparece. É o que o índice precisa para enxergar o
    cadastro que outra estação gravou noutro paciente (ver ``_ainda_vale``).
    ``erros`` recolhe as pastas que não deram para ler, e é o que impede o
    índice de guardar uma varredura pela metade.
    """
    achadas = []
    if pais is not None:
        pais[base] = _marca_de(base)
    for pasta in _subpastas(base, erros):
        if _e_gaveta(os.path.basename(pasta)):
            if pais is not None:
                pais[pasta] = _marca_de(pasta)
            achadas.extend(_subpastas(pasta, erros))
        else:
            achadas.append(pasta)
    return achadas


def _subpastas(base: str, erros: Optional[list] = None) -> list[str]:
    """Subpastas de ``base``, ou lista vazia se ela não puder ser lida.

    Uma pasta sem permissão não pode derrubar a varredura inteira: com o
    ``os.scandir`` aberto num try único, um só erro descartava todos os
    candidatos e o app respondia "esse paciente não tem simulação" para todo
    mundo. O ``with`` também garante que o iterador feche no Windows, onde ele
    segura o diretório.

    Engolir o erro era certo enquanto a varredura era refeita a cada busca — o
    problema se curava na navegação seguinte. Com o índice guardando o
    resultado, deixou de se curar: por isso ``erros`` existe, e é conferido
    antes de guardar.
    """
    try:
        with os.scandir(base) as it:
            return [e.path for e in it if e.is_dir()]
    except OSError:
        _LOG.info("Não consegui ler %s ao procurar simulações", base)
        if erros is not None:
            erros.append(base)
        return []


def _identificacao(pasta: str) -> Optional[tuple[str, str]]:
    """(registro, nome) do cadastro, sem carregar as fotos."""
    caminho = os.path.join(pasta, ARQ_CADASTRO)
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as fh:
            pac = (json.load(fh).get("paciente") or {})
    except (OSError, ValueError):
        return None
    return pac.get("registro", ""), pac.get("nome", "")


def _ordem_mes(nome: str) -> tuple[int, int]:
    """``"08-2026"`` → ``(2026, 8)``, para achar a simulação mais recente."""
    m = re.match(r"^(\d{1,2})-(\d{4})$", nome.strip())
    return (int(m.group(2)), int(m.group(1))) if m else (0, 0)


def historico(nome: str, registro: str = "") -> list[str]:
    """Todas as pastas de simulação do paciente, da mais recente para a antiga."""
    # Os DOIS lugares, somados: um paciente que já tinha pasta na raiz e voltou
    # depois da gaveta tem meses dos dois lados. Olhar só um deles esconderia
    # metade do histórico — e é o histórico que diz se houve replanejamento.
    novo = pasta_do_paciente(nome, registro)
    antigo = os.path.join(raiz(), os.path.basename(novo))
    meses = []
    for pasta_pac in (novo, antigo):
        if not os.path.isdir(pasta_pac):
            continue
        try:
            meses += [os.path.join(pasta_pac, e.name)
                      for e in os.scandir(pasta_pac) if e.is_dir()]
        except OSError:
            continue
    return sorted(meses, key=lambda c: _ordem_mes(os.path.basename(c)),
                  reverse=True)
