"""Relatórios exportados que alimentam a **Capa de Tratamento**.

A ficha técnica nasce do DICOM; a capa não. Convênio, contato, curso, intenção,
CID, médico assistente e as linhas de prescrição aprovadas vêm de três
relatórios exportados para uma pasta, e é deles que esta tela lê:

``Capa_de_Tratamento_Periodo.csv``
    Uma linha por paciente EM TRATAMENTO — o cadastro (nome, DDN, sexo, contato,
    convênio, curso, intenção, CID, máquina, médico).
``Capa_Prescrições por Período.csv``
    Uma linha por prescrição aprovada — vários pacientes têm mais de uma (mama +
    boost), e todas entram na capa, na ordem em que saem do relatório.
``Capa_Todos_Foto_ID_Nome.mhtml``
    A foto 3×4 do paciente — uma linha por paciente, com a imagem embutida
    (ver :func:`foto_do_paciente`).

Os três são LIDOS, nunca escritos. Cada um é um retrato do dia em que foi
exportado: se o paciente não aparece nele, a capa sai com os campos vazios para
quem está fazendo a ficha preencher — nunca com dado inventado.

O casamento é por **ID e nome**, nessa ordem de confiança: o ID acha, o nome
confirma. ID que acha um cadastro cujo nome não bate devolve o cadastro **com
aviso** — quem decide se é homônimo, erro de digitação ou o paciente certo com o
nome grafado de outro jeito é a pessoa, não o programa.

A folha 2 tem outra fonte, que não é relatório nenhum: a **nota de
posicionamento** que o técnico escreve e deixa na pasta do paciente, junto do
DICOM (ver :func:`interpretar_notas`).
"""
from __future__ import annotations

import base64
import csv
import logging
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from isocentro import raiz
from isocentro.dados import ambiente
# Reexportado de propósito: ver a nota em "Normalização de nome", abaixo.
from isocentro.dados.nomes import como_nome_proprio, de_pessoa, desinverter  # noqa: F401

_LOG = logging.getLogger(__name__)

# ── Onde estão os relatórios ─────────────────────────────────────────────────
# Mesma convenção do resto do app (ISOCENTRO_USERS_DIR, ISOCENTRO_BACKUP_DIR): a
# variável de ambiente manda, e sem ela vale a subpasta ``capa/`` ao lado do
# programa. Assim a estação aponta para o compartilhamento onde as exportações
# são despejadas, sem que ninguém precise reempacotar o executável.
PASTA_ENV = "ISOCENTRO_CAPA_DIR"

ARQ_CADASTRO = "Capa_de_Tratamento_Periodo.csv"
ARQ_PRESCRICOES = "Capa_Prescrições por Período.csv"
ARQ_FOTOS = "Capa_Todos_Foto_ID_Nome.mhtml"

# O relatório sai em UTF-8 com BOM. Quem exporta pode um dia salvar em
# Windows-1252 (é um clique no Reporting Services), e um acento torto é bem
# melhor do que a capa indisponível — por isso a leitura cai para latin-1, que
# nunca levanta erro de decodificação, em vez de desistir.
_ENCODINGS = ("utf-8-sig", "latin-1")

# Linhas de preâmbulo do CSV de cadastro antes do cabeçalho (título, período em
# branco). O cabeçalho real é a 4ª linha (``d_0,d_1,…``).
_PREAMBULO_CADASTRO = 3

# O que a capa imprime quando o preparo não se aplica. Fonte única: o
# ``capa_pdf`` reusa este, e a interpretação da nota já o produz.
VAZIO_PREPARO = "N/A"

# Texto único porque a tela precisa RECONHECÊ-LO: no momento da tomografia não
# existe prescrição aprovada, e este aviso ali é ruído — a coisa certa
# acontecendo, pintada de vermelho.
# De onde saiu o que está na tela (``Resultado.origem``).
#
# A partir de 18/08/2026 a fonte do serviço é o BANCO. Os relatórios exportados
# continuam no código, mas como RESERVA DE EMERGÊNCIA — e emergência que se usa
# sem avisar deixa de ser emergência e vira o normal.
#
# O risco é concreto: ninguém mais vai reexportar os CSV. Cada dia que passa,
# eles ficam mais velhos, e um retrato de três semanas traz o convênio que já
# mudou e a prescrição que já foi revista. Por isso a idade deles vai para a
# tela, em anos-luz do "a capa saiu, deve estar certa".
ORIGEM_BANCO = "banco (variandw)"
# O banco GRAVADO (``banco_local.py``), que só existe em máquina de trabalho.
# Origem própria, e não ``ORIGEM_BANCO``: a tela mostra este texto, e dizer
# "banco (variandw)" para um arquivo gravado semana passada é exatamente a
# reserva silenciosa que este projeto não aceita.
ORIGEM_BANCO_LOCAL = "banco LOCAL gravado (SIMULAÇÃO)"
ORIGEM_ESPELHO = "espelho local"
ORIGEM_RELATORIOS = "relatórios exportados"

# A partir de quantos dias o retrato exportado deixa de ser "de ontem" e passa a
# merecer um aviso forte. Um curso muda de prescrição em dias, não em meses.
_DIAS_RELATORIO_VELHO = 7

AVISO_SEM_PRESCRICAO = (
    "Nenhuma prescrição aprovada no relatório para este paciente.")


# Pasta escolhida na tela (ver ``definir_pasta_dados``). Mora aqui, e não num
# QSettings lido daqui, para este módulo continuar sem saber que existe uma
# interface — quem persiste a escolha é a janela.
_pasta_escolhida = ""


def definir_pasta_dados(caminho: str) -> None:
    """Aponta a pasta dos relatórios. "" volta ao padrão (e reabre a procura)."""
    global _pasta_escolhida, _pasta_procurada
    _pasta_escolhida = str(caminho or "").strip()
    _pasta_procurada = None


def _app_dir() -> str:
    """Pasta do programa. No executável é a do .exe, não a do bundle temporário
    do PyInstaller, onde ninguém conseguiria largar um relatório novo.

    Delega ao ``raiz.pasta_do_app``. A conta antiga era
    ``dirname(__file__)``, e dava a resposta certa por COINCIDÊNCIA DE LUGAR:
    o módulo morava na raiz do projeto. De ``isocentro/banco/`` ela daria
    dois níveis abaixo, sem erro nenhum — a procura automática varreria a
    pasta errada e diria que não há relatório.
    """
    return str(raiz.pasta_do_app())


# Pastas que a procura automática nunca abre: ou são grandes e sem relatório
# nenhum, ou são do controle de versão.
_IGNORAR = {".git", ".venv", "venv", "build", "dist", "__pycache__",
            ".pytest_cache", "node_modules", "assets", ".vscode", ".claude"}

# Até onde a procura desce a partir da pasta do programa. Três níveis pegam
# ``capa/``, ``banco de dados/`` e ``TCs_Teste/banco de dados/`` sem varrer o
# disco inteiro.
_PROFUNDIDADE_PROCURA = 3

# Resultado da procura, para ela rodar uma vez por sessão. ``None`` = ainda não
# procurou; "" = procurou e não achou.
_pasta_procurada: Optional[str] = None


def _procurar_relatorios() -> str:
    """Acha, sob a pasta do programa, um diretório com o CSV de cadastro.

    Existe porque o caminho padrão (``capa/``) é uma convenção que ninguém é
    obrigado a conhecer: quem recebe os relatórios os salva onde faz sentido
    para ele, e uma capa vazia não explica que o problema era o nome da pasta.
    A procura é rasa, ignora as pastas grandes e roda uma vez por sessão.
    """
    base = _app_dir()
    fila = [(base, 0)]
    while fila:
        pasta, nivel = fila.pop(0)
        try:
            entradas = list(os.scandir(pasta))
        except OSError:
            continue
        if any(e.is_file() and e.name == ARQ_CADASTRO for e in entradas):
            return pasta
        if nivel >= _PROFUNDIDADE_PROCURA:
            continue
        for e in entradas:
            if e.is_dir() and e.name not in _IGNORAR and not e.name.startswith("."):
                fila.append((e.path, nivel + 1))
    return ""


def pasta_dados() -> str:
    """Pasta de onde saem os relatórios exportados.

    Cinco fontes, nesta ordem:

    1. a **escolhida nesta sessão** (``definir_pasta_dados``);
    2. a variável de ambiente ``ISOCENTRO_CAPA_DIR`` — decisão de instalação, de
       quem montou a estação, e por isso acima da configuração remota;
    3. a **configuração do serviço** (:mod:`config_servico`), que é o que o
       admin aponta uma vez e vale para TODAS as estações. Antes esta escolha
       morava no ``QSettings``, que é por usuário do Windows e por máquina: o
       admin apontava a pasta certa e a estação ao lado continuava sem achar
       relatório nenhum;
    4. a subpasta ``capa/`` ao lado do programa;
    5. o que a procura automática encontrar (ver :func:`_procurar_relatorios`).
    """
    global _pasta_procurada
    if _pasta_escolhida:
        return _pasta_escolhida
    env = ambiente.ler(PASTA_ENV)
    if env:
        return env
    do_servico = _do_servico()
    if do_servico:
        return do_servico
    padrao = os.path.join(_app_dir(), "capa")
    if os.path.exists(os.path.join(padrao, ARQ_CADASTRO)):
        return padrao
    if _pasta_procurada is None:
        _pasta_procurada = _procurar_relatorios()
    return _pasta_procurada or padrao


def _do_servico() -> str:
    """A pasta que o admin apontou para o serviço inteiro ("" se não houver)."""
    try:
        from isocentro.dados import config_servico
        return config_servico.valor(config_servico.PASTA_RELATORIOS)
    except Exception:  # noqa: BLE001 — sem configuração, segue nos padrões
        return ""


def origem_da_pasta() -> str:
    """De ONDE veio a pasta em uso — para a tela poder dizer.

    Sem isto, a pessoa que aponta a pasta e não vê efeito nenhum não tem como
    descobrir que uma variável de ambiente na estação está mandando nela.
    """
    if _pasta_escolhida:
        return "escolhida nesta sessão"
    # O NOME que venceu, não o nome antigo genérico: numa estação com as duas
    # variáveis definidas, dizer "ISOCENTRO_CAPA_DIR" mandaria o admin conferir a
    # errada.
    qual = ambiente.qual_valeu(PASTA_ENV)
    if qual:
        return f"variável {qual} desta estação"
    if _do_servico():
        return "configuração do serviço"
    padrao = os.path.join(_app_dir(), "capa")
    if os.path.exists(os.path.join(padrao, ARQ_CADASTRO)):
        return "subpasta capa/ do programa"
    return "procura automática"


def relatorios_presentes() -> list[str]:
    """Quais dos três relatórios estão na pasta agora — para a tela dizer."""
    return [n for n in (ARQ_CADASTRO, ARQ_PRESCRICOES, ARQ_FOTOS)
            if os.path.exists(_arquivo(n))]


def _arquivo(nome: str) -> str:
    return os.path.join(pasta_dados(), nome)


def _linhas_csv(caminho: str) -> list[list[str]]:
    """Lê o CSV inteiro, tentando os encodings prováveis em ordem."""
    for enc in _ENCODINGS:
        try:
            with open(caminho, encoding=enc, newline="") as fh:
                return list(csv.reader(fh))
        except UnicodeDecodeError:
            continue
    return []


# ── Limites de mês (resumos mensais da Agenda) ──────────────────────────────

def limites_do_mes(referencia: date) -> tuple[date, date]:
    """``(inicio, fim)`` do mês de ``referencia`` pelo CALENDÁRIO — do dia 1
    ao dia 1 do mês seguinte (``fim`` exclusivo) — nunca uma janela de 30
    dias corridos. Usado pelos resumos mensais da Agenda em
    ``agenda_db``/``tratamento_db``, que precisam do mesmo período para os
    dois números lado a lado não divergirem."""
    inicio = referencia.replace(day=1)
    if inicio.month == 12:
        fim = inicio.replace(year=inicio.year + 1, month=1)
    else:
        fim = inicio.replace(month=inicio.month + 1)
    return inicio, fim


# ── Normalização de nome ─────────────────────────────────────────────────────

def _sem_acento(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s)
                   if unicodedata.category(ch) != "Mn")


def normalizar_nome(nome: str) -> str:
    """Forma comparável de um nome: sem acento, maiúsculo, espaço único."""
    s = _sem_acento(str(nome or "")).upper()
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalizar_id(registro: str) -> str:
    """Forma comparável de um ID/RGH: só letras e dígitos, maiúsculo.

    O mesmo registro aparece como ``9000018ANA`` no relatório e às vezes com
    espaço ou traço na digitação — a comparação não pode depender disso.
    """
    return re.sub(r"[^A-Z0-9]", "", str(registro or "").upper())


# A GRAFIA do nome (``desinverter``, ``como_nome_proprio``, ``de_pessoa``)
# mudou-se para ``nomes.py``: ela vale para o app inteiro, e ``dicom_rt``, que
# também precisa dela, não pode depender deste módulo — que lê CSV e importa o
# DICOM de volta. Os três continuam acessíveis como ``capa_dados.<nome>`` (o
# import está no topo) porque meio repositório os chama assim.


# ── Cadastro (Capa_de_Tratamento_Periodo.csv) ────────────────────────────────
# As colunas saem do relatório com nomes opacos (d_0, d_1, …) porque quem o
# montou não as nomeou. A posição é estável, então o índice é o contrato.
_C_ID = 0
_C_NOME = 1
_C_DDN = 2
_C_SEXO = 3
_C_CONTATO = 4
_C_CONVENIO = 5
_C_NUM_CONVENIO = 6
_C_CURSO = 7
_C_STATUS = 8
_C_INTENCAO = 9
_C_CID_DESC = 10
_C_MAQUINA = 13
_C_MEDICO = 24


@dataclass
class Cadastro:
    """Uma linha do relatório de cadastro, já em português da capa."""
    registro: str = ""
    nome: str = ""
    nascimento: str = ""
    sexo: str = ""
    contato: str = ""
    convenio: str = ""
    curso: str = ""
    intencao: str = ""
    cid: str = ""
    descricao: str = ""
    maquina: str = ""
    medico: str = ""
    status: str = ""        # ATIVO, ALTA… — diz se o curso ainda está correndo

    def curso_ativo(self) -> bool:
        return self.status.strip().upper().startswith("ATIVO")


def _split_cid(texto: str) -> tuple[str, str]:
    """``"C50.9 Neoplasia maligna da mama"`` → ``("C50.9", "Neoplasia …")``.

    O relatório junta código e descrição num campo só. Sem código reconhecível,
    o texto inteiro vira descrição — a capa mostra o que tem, e o campo CID sai
    vazio para quem estiver conferindo preencher.
    """
    t = str(texto or "").strip()
    m = re.match(r"^([A-Z]\d{2}(?:\.\d+)?)\s+(.*)$", t)
    return (m.group(1), m.group(2).strip()) if m else ("", t)


def _convenio(nome: str, numero: str) -> str:
    """``"SUS"`` + o nº da carteirinha → ``"SUS - 700000000000000"``."""
    n, num = str(nome or "").strip(), str(numero or "").strip()
    if n and num:
        return f"{n} - {num}"
    return n or num


def carregar_cadastro() -> dict[str, Cadastro]:
    """Todo o cadastro, indexado pelo ID normalizado. Ausente = dict vazio."""
    caminho = _arquivo(ARQ_CADASTRO)
    if not os.path.exists(caminho):
        _LOG.info("Relatório de cadastro não encontrado em %s", caminho)
        return {}
    out: dict[str, Cadastro] = {}
    try:
        # +1 pelo cabeçalho d_0,d_1,… que vem depois do preâmbulo.
        for linha in _linhas_csv(caminho)[_PREAMBULO_CADASTRO + 1:]:
            if len(linha) <= _C_MAQUINA or not linha[_C_ID].strip():
                continue                            # rodapé de totais
            cid, desc = _split_cid(_col(linha, _C_CID_DESC))
            reg = linha[_C_ID].strip()
            out[normalizar_id(reg)] = Cadastro(
                registro=reg,
                nome=de_pessoa(_col(linha, _C_NOME)),
                nascimento=_col(linha, _C_DDN),
                sexo=_col(linha, _C_SEXO),
                contato=_col(linha, _C_CONTATO),
                convenio=_convenio(_col(linha, _C_CONVENIO),
                                   _col(linha, _C_NUM_CONVENIO)),
                curso=_col(linha, _C_CURSO),
                intencao=_col(linha, _C_INTENCAO),
                cid=cid, descricao=desc,
                maquina=_col(linha, _C_MAQUINA),
                medico=_col(linha, _C_MEDICO),
                status=_col(linha, _C_STATUS),
            )
    except Exception:  # noqa: BLE001 — a capa sai vazia, não sai quebrada
        _LOG.exception("Falha ao ler %s", caminho)
        return {}
    return out


def _col(linha: list, i: int) -> str:
    return linha[i].strip() if i < len(linha) else ""


# ── Prescrições (Prescrições por Período.csv) ────────────────────────────────
_P_ID = 0
_P_NOME = 1
_P_DESCRICAO = 2
_P_SITE = 3
_P_CURSO = 4
_P_VOLUMES = 5
_P_DOSES = 6
_P_DOSE_FRAC = 7
_P_FRACOES = 8
_P_FREQUENCIA = 9
_P_TECNICA = 10
_P_STATUS = 11
_P_APROVADOR = 12
_P_DATA = 13

# Sítios anatômicos como o relatório os grava (inglês, e às vezes já em português
# quando alguém digitou na mão). Só os que aparecem de fato no serviço — o que
# não estiver aqui sai como veio, que é mais honesto do que traduzir por
# adivinhação e imprimir a região errada na capa.
SITES_PT: dict[str, str] = {
    "abdomen": "Abdome", "anus": "Ânus", "arm, left": "Braço, esquerdo",
    "arm, right": "Braço, direito", "axilla, left": "Axila, esquerda",
    "axilla, right": "Axila, direita", "bladder": "Bexiga", "brain": "Encéfalo",
    "breast, left": "Mama, esquerda", "breast, right": "Mama, direita",
    "cervix": "Colo do útero", "cranium": "Crânio",
    "deep cervical chain nodes": "Cadeia cervical profunda",
    "esophagus": "Esôfago", "face": "Face", "femur left": "Fêmur, esquerdo",
    "femur right": "Fêmur, direito", "humerus, left": "Úmero, esquerdo",
    "humerus, right": "Úmero, direito",
    "infraclavicular nodes": "Linfonodos infraclaviculares",
    "internal iliac nodes": "Linfonodos ilíacos internos",
    "larynx": "Laringe", "leg, left": "Perna, esquerda",
    "leg, right": "Perna, direita", "lip, lower": "Lábio inferior",
    "liver": "Fígado", "lung, left": "Pulmão, esquerdo",
    "lung, right": "Pulmão, direito", "nasopharynx": "Nasofaringe",
    "neck": "Pescoço", "neck left": "Pescoço, esquerdo",
    "neck right": "Pescoço, direito", "nipple, right": "Mamilo, direito",
    "nipple, left": "Mamilo, esquerdo", "nose": "Nariz",
    "oesophagus": "Esôfago", "oropharynx": "Orofaringe", "pancreas": "Pâncreas",
    "parotid, left": "Parótida, esquerda", "parotid, right": "Parótida, direita",
    "pelvis": "Pelve", "pharynx": "Faringe", "prostate": "Próstata",
    "prostate and seminal vessicles.": "Próstata e vesículas seminais",
    "rectum": "Reto", "ribs, left": "Arcos costais, esquerdos",
    "ribs, right": "Arcos costais, direitos", "sacrum": "Sacro",
    "scalp": "Couro cabeludo", "scapula, left": "Escápula, esquerda",
    "scapula, right": "Escápula, direita",
    "seminal vesicles": "Vesículas seminais", "stomach": "Estômago",
    "thigh": "Coxa", "thorax": "Tórax", "tongue": "Língua",
    "total body": "Corpo total", "uterus": "Útero", "vagina": "Vagina",
    "vertebrae, cervical": "Vértebras cervicais",
    "vertebrae, lumbar": "Vértebras lombares",
    "vertebrae, thoracic": "Vértebras torácicas",
    # ── Cabeça e pescoço ──
    "buccal mucosa": "Mucosa jugal", "canthus, right outer": "Canto externo, direito",
    "cheek, left": "Bochecha, esquerda", "cheek, right": "Bochecha, direita",
    "eye, left": "Olho, esquerdo", "eye, right": "Olho, direito",
    "hard palate": "Palato duro", "soft palate": "Palato mole",
    "laryngopharynx": "Laringofaringe", "lip, upper": "Lábio superior",
    "mandible": "Mandíbula", "maxilla": "Maxila",
    "maxillary antrum": "Seio maxilar", "middle ear": "Ouvido médio",
    "orbit left": "Órbita, esquerda", "orbit right": "Órbita, direita",
    "paranasal sinus": "Seio paranasal", "pinna, left": "Pavilhão auricular, esquerdo",
    "pinna, right": "Pavilhão auricular, direito", "pituitary": "Hipófise",
    "pineal gland": "Glândula pineal", "post-cricoid": "Retrocricoide",
    "sublingual glands": "Glândulas sublinguais",
    "submandibular glands": "Glândulas submandibulares",
    "submandibular nodes": "Linfonodos submandibulares",
    "thyroid": "Tireoide", "tonsil, right": "Amígdala, direita",
    "tonsil, left": "Amígdala, esquerda", "trachea": "Traqueia",
    "meninges": "Meninges", "thymus": "Timo",
    # ── Tronco e vísceras ──
    "back": "Dorso", "bronchus, right": "Brônquio, direito",
    "bronchus, left": "Brônquio, esquerdo",
    "chest wall, left": "Parede torácica, esquerda",
    "chest wall, right": "Parede torácica, direita", "colon": "Cólon",
    "duodenum": "Duodeno", "heart": "Coração",
    "hemi-body, lower": "Hemicorpo inferior",
    "hemi-body, upper": "Hemicorpo superior",
    "kidney, left": "Rim, esquerdo", "kidney, right": "Rim, direito",
    "adrenal gland, left": "Suprarrenal, esquerda",
    "adrenal gland, right": "Suprarrenal, direita",
    "ovary, left": "Ovário, esquerdo", "ovary, right": "Ovário, direito",
    "spleen": "Baço", "testis": "Testículo", "total skin": "Pele total",
    "ureter, right": "Ureter, direito", "ureter, left": "Ureter, esquerdo",
    "vulva": "Vulva", "penis": "Pênis", "penis, glans": "Glande",
    "bone marrow (diffuse)": "Medula óssea (difusa)",
    # ── Coluna e medula ──
    "cervical spine": "Coluna cervical", "lumbar spine": "Coluna lombar",
    "thoracic spine": "Coluna torácica", "coccyx": "Cóccix",
    "spinal cord": "Medula espinhal",
    "spinal cord, cervical": "Medula espinhal, cervical",
    "spinal cord, lumbar": "Medula espinhal, lombar",
    "spinal cord, thoracic": "Medula espinhal, torácica",
    "vertebrae, sacral": "Vértebras sacrais",
    # ── Pelve e membros ──
    "fibula, right": "Fíbula, direita", "fibula, left": "Fíbula, esquerda",
    "foot, left": "Pé, esquerdo", "foot, right": "Pé, direito",
    "forearm, left": "Antebraço, esquerdo", "forearm, right": "Antebraço, direito",
    "hand, left": "Mão, esquerda", "hand, right": "Mão, direita",
    "hip, left": "Quadril, esquerdo", "hip, right": "Quadril, direito",
    "ilium, left": "Ilíaco, esquerdo", "ilium, right": "Ilíaco, direito",
    "ischium": "Ísquio", "knee, left": "Joelho, esquerdo",
    "knee, right": "Joelho, direito", "pubis, left": "Púbis, esquerdo",
    "pubis, right": "Púbis, direito", "radius, left": "Rádio, esquerdo",
    "radius, right": "Rádio, direito", "sacro-iliac joints": "Articulações sacroilíacas",
    "sacro-iliac, left": "Sacroilíaca, esquerda",
    "sacro-iliac, right": "Sacroilíaca, direita",
    "tibia, left": "Tíbia, esquerda", "tibia, right": "Tíbia, direita",
    "ulna, left": "Ulna, esquerda", "ulna, right": "Ulna, direita",
    # ── Cadeias linfáticas ──
    "deep inguinal nodes": "Linfonodos inguinais profundos",
    "superficial inguinal nodes": "Linfonodos inguinais superficiais",
    "para-sternal nodes": "Linfonodos paraesternais",
    "pre-sacral nodes": "Linfonodos pré-sacrais",
    "external iliac nodes": "Linfonodos ilíacos externos",
    # ── Já em português no relatório: só a acentuação é acertada ──
    "abdômen": "Abdome", "acetabulo direito": "Acetábulo, direito",
    "acetabulo esquerdo": "Acetábulo, esquerdo",
    "adrenal direita": "Suprarrenal, direita",
    "adrenal esquerda": "Suprarrenal, esquerda",
    "assoalho bucal": "Assoalho bucal", "cérebro": "Encéfalo",
    "clavicula d": "Clavícula, direita", "clavicula e": "Clavícula, esquerda",
    "conduto auditivo interno direito": "Conduto auditivo interno, direito",
    "conduto auditivo interno esquerdo": "Conduto auditivo interno, esquerdo",
    "diafragma": "Diafragma", "esterno": "Esterno",
    "fossa supraclavicular direita": "Fossa supraclavicular, direita",
    "fossa supraclavicular esquerda": "Fossa supraclavicular, esquerda",
    "hipofise": "Hipófise", "iliaco direito": "Ilíaco, direito",
    "iliaco esquerdo": "Ilíaco, esquerdo", "inguinais": "Inguinais",
    "isquio direito": "Ísquio, direito", "isquio esquerdo": "Ísquio, esquerdo",
    "leito prostatico": "Leito prostático",
    "linfonodo iliaco externo": "Linfonodo ilíaco externo",
    "linfonodos da cadeia cervical profunda": "Cadeia cervical profunda",
    "mama bilateral": "Mama bilateral", "mamaria interna": "Mamária interna",
    "mento": "Mento", "oligomets": "Oligometástases",
    "ombro d": "Ombro, direito", "ombro e": "Ombro, esquerdo",
    "pele ouvido": "Pele da orelha",
}

# Frequência de aplicação. O relatório mistura inglês de fábrica com o que a equipe
# digitou; a capa imprime sempre em português.
FREQUENCIAS_PT: dict[str, str] = {
    "once daily": "Uma Vez por Dia",
    "twice daily": "Duas Vezes por Dia",
    "dias alternado": "Dias Alternados",
    "aplicação unica": "Aplicação Única",
    "duas vezes por semana": "Duas Vezes por Semana",
}


def traduzir_site(site: str) -> str:
    return SITES_PT.get(str(site or "").strip().lower(), str(site or "").strip())


def traduzir_frequencia(freq: str) -> str:
    chave = _sem_acento(str(freq or "").strip().lower())
    for k, v in FREQUENCIAS_PT.items():
        if _sem_acento(k) == chave:
            return v
    return str(freq or "").strip()


@dataclass
class Volume:
    """Um alvo prescrito: nome, dose total e dose por fração, já em cGy."""
    nome: str = ""
    dose_cgy: str = ""
    dose_frac_cgy: str = ""

    def linha(self) -> str:
        return f"Volume {self.nome}  {self.dose_cgy} cGy  {self.dose_frac_cgy} cGy/Frac"


@dataclass
class Prescricao:
    """Uma prescrição aprovada — vira um bloco no corpo da capa."""
    site: str = ""
    descricao: str = ""
    volumes: list[Volume] = field(default_factory=list)
    fracoes: str = ""
    frequencia: str = ""
    # A nota que o radioterapeuta escreveu na prescrição (estadiamento, "após
    # QT", o que condiciona o tratamento). Sai à direita do bloco na capa
    # impressa — ver ``capa_pdf._prescricoes``. O relatório CSV não a exporta,
    # então ela só existe quando a capa vem do BANCO.
    notas: str = ""
    aprovador: str = ""
    data_aprovacao: str = ""
    curso: str = ""
    # Identificação como veio no relatório — a lista de pacientes da tela de
    # Simulação sai daqui quando o paciente ainda não está no cadastro.
    registro_bruto: str = ""
    nome_bruto: str = ""

    def titulo(self) -> str:
        """``"Mama, esquerda: Mama + FSC E 40,05Gy@15fx"``."""
        if self.site and self.descricao:
            return f"{self.site}: {self.descricao}"
        return self.site or self.descricao

    def linha_frequencia(self) -> str:
        if not self.fracoes:
            return self.frequencia
        plural = "frações" if self.fracoes.strip() != "1" else "fração"
        return f"{self.fracoes} {plural} - {self.frequencia}".rstrip(" -")


def _gy_para_cgy(texto: str) -> str:
    """``"40.05 Gy"`` → ``"4005"``. Devolve o texto original se não for dose.

    A capa imprime tudo em cGy; o relatório traz em Gy com ponto decimal. O
    resultado sai sem casas quando é inteiro (4005, não 4005.0) — é assim que o
    modelo mostra, e a fração de cGy não tem significado clínico aqui.
    """
    t = str(texto or "").strip()
    m = re.match(r"^([\d.,]+)\s*Gy$", t, re.IGNORECASE)
    if not m:
        return t
    try:
        valor = float(m.group(1).replace(",", ".")) * 100
    except ValueError:
        return t
    return f"{valor:.0f}" if abs(valor - round(valor)) < 0.05 else f"{valor:.1f}"


def _lista(campo: str) -> list[str]:
    """Separa os campos multivalorados (``"PTV_Mama_E, PTV_FSC_E"``)."""
    return [p.strip() for p in str(campo or "").split(",") if p.strip()]


def _prescricao_da_linha(linha: list) -> Prescricao:
    nomes = _lista(_col(linha, _P_VOLUMES))
    doses = _lista(_col(linha, _P_DOSES))
    frac = _lista(_col(linha, _P_DOSE_FRAC))
    volumes = [Volume(nome=n,
                      dose_cgy=_gy_para_cgy(doses[i] if i < len(doses) else ""),
                      dose_frac_cgy=_gy_para_cgy(frac[i] if i < len(frac) else ""))
               for i, n in enumerate(nomes)]
    return Prescricao(
        site=traduzir_site(_col(linha, _P_SITE)),
        descricao=_col(linha, _P_DESCRICAO),
        volumes=volumes,
        fracoes=_col(linha, _P_FRACOES),
        frequencia=traduzir_frequencia(_col(linha, _P_FREQUENCIA)),
        aprovador=_col(linha, _P_APROVADOR),
        data_aprovacao=_col(linha, _P_DATA),
        curso=_col(linha, _P_CURSO),
        registro_bruto=_col(linha, _P_ID),
        nome_bruto=_col(linha, _P_NOME),
    )


def carregar_prescricoes() -> dict[str, list[Prescricao]]:
    """Prescrições por ID normalizado, na ordem em que saem do relatório."""
    caminho = _arquivo(ARQ_PRESCRICOES)
    if not os.path.exists(caminho):
        _LOG.info("Relatório de prescrições não encontrado em %s", caminho)
        return {}
    out: dict[str, list[Prescricao]] = {}
    try:
        for linha in _linhas_csv(caminho)[1:]:      # [0] é o cabeçalho col0,col1,…
            if len(linha) <= _P_DATA or not linha[_P_ID].strip():
                continue
            out.setdefault(normalizar_id(linha[_P_ID]), []).append(
                _prescricao_da_linha(linha))
    except Exception:  # noqa: BLE001
        _LOG.exception("Falha ao ler %s", caminho)
        return {}
    return out


# ── Foto do paciente (Capa_Todos_Foto_ID_Nome.mhtml) ─────────────────────────
# O relatório exporta em MHTML: um MIME ``multipart/related`` com o HTML na
# primeira parte e UMA PARTE POR IMAGEM, cada uma com o seu ``Content-ID``. A
# tabela do HTML tem três colunas — Foto, ID do Paciente, Nome do Paciente — e a
# célula da foto é um ``<IMG SRC="cid:UUID">`` apontando para a parte.
#
# O arquivo tem ~190 MB e ~4 700 pacientes. Ler tudo para pegar UMA foto seria
# despejar o relatório inteiro na memória a cada capa, então são duas passagens:
# a primeira decodifica só o HTML (3 MB) e monta o índice ``ID → Content-ID``; a
# segunda varre o arquivo atrás daquele Content-ID e decodifica **só** a parte
# dele.
#
# As tags vêm em MAIÚSCULAS (``<TR>``, ``<TD>``, ``SRC=``): é como o SSRS
# escreve, e um regex em minúsculas não casa nada.

_BOUNDARY = b"------=_NextPart"
_RE_LINHA_MHTML = re.compile(r"<TR[^>]*>(.*?)</TR>", re.DOTALL | re.IGNORECASE)
_RE_CELULA_MHTML = re.compile(r"<TD[^>]*>(.*?)</TD>", re.DOTALL | re.IGNORECASE)
_RE_CID = re.compile(r'SRC="cid:([^"]+)"', re.IGNORECASE)
_RE_CONTENT_ID = re.compile(rb"Content-ID:\s*<([^>]+)>", re.IGNORECASE)
_RE_TAG = re.compile(r"<[^>]+>")

# Índice em cache: montá-lo custa a decodificação do HTML, e uma capa pede a
# foto de um paciente só. A chave é ``(mtime, tamanho)`` — relatório novo na
# mesma pasta tem de invalidar o cache sem ninguém reiniciar o programa.
_indice_fotos: dict = {}


def _partes_mhtml(caminho: str):
    """Percorre o MHTML devolvendo ``(cabeçalho, corpo_base64)`` por parte.

    Em FLUXO, linha a linha: o arquivo tem centenas de megabytes, e lê-lo
    inteiro para achar uma foto é exatamente o que este desenho evita.
    """
    cab: list = []
    corpo: list = []
    dentro = False
    with open(caminho, "rb") as f:
        for linha in f:
            crua = linha.rstrip(b"\r\n")
            if crua.startswith(_BOUNDARY):
                if cab or corpo:
                    yield b"\n".join(cab), b"".join(corpo)
                cab, corpo, dentro = [], [], False
                continue
            if not dentro:
                if crua == b"":
                    dentro = True
                else:
                    cab.append(crua)
                continue
            corpo.append(crua)
    if cab or corpo:
        yield b"\n".join(cab), b"".join(corpo)


def _content_id(cabecalho: bytes) -> str:
    m = _RE_CONTENT_ID.search(cabecalho)
    return m.group(1).decode("utf-8", "replace").strip() if m else ""


def _indice_de_fotos(caminho: str) -> dict:
    """``{"id": {ID: cid}, "nome": {NOME: cid}}`` do relatório.

    O nome entra junto porque o ID nem sempre casa (paciente recém-cadastrado,
    ID grafado de outro jeito) — mas em chave separada, para o casamento por
    nome continuar exigindo coincidência exata.
    """
    try:
        estampa = (os.path.getmtime(caminho), os.path.getsize(caminho))
    except OSError:
        return {"id": {}, "nome": {}}
    if _indice_fotos.get("_estampa") == estampa:
        return _indice_fotos["dados"]

    por_id: dict = {}
    por_nome: dict = {}
    for cab, corpo in _partes_mhtml(caminho):
        if b"text/html" not in cab.lower():
            continue
        try:
            html = base64.b64decode(corpo).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 — relatório torto não derruba a capa
            _LOG.exception("MHTML de fotos ilegível em %s", caminho)
            break
        for linha in _RE_LINHA_MHTML.findall(html):
            celulas = _RE_CELULA_MHTML.findall(linha)
            if len(celulas) < 3:
                continue
            cid = _RE_CID.search(celulas[0])
            if not cid:
                continue          # cabeçalho da tabela e a faixa do logo
            # O ``cid`` vem com quebra de linha no fim em parte das linhas.
            alvo = cid.group(1).strip()
            ident = _RE_TAG.sub(" ", celulas[1]).strip()
            nome = _RE_TAG.sub(" ", celulas[2]).strip()
            if ident:
                por_id.setdefault(normalizar_id(ident), alvo)
            if nome:
                # O relatório escreve "Sobrenome, Nome"; o resto do app fala na
                # ordem direta.
                por_nome.setdefault(normalizar_nome(desinverter(nome)), alvo)
        break                     # o HTML é a 1ª parte; o resto é imagem

    dados = {"id": por_id, "nome": por_nome}
    _indice_fotos.clear()
    _indice_fotos.update({"_estampa": estampa, "dados": dados})
    return dados


def _imagem_por_cid(caminho: str, alvo: str) -> Optional[bytes]:
    """Os bytes da parte cujo ``Content-ID`` é ``alvo``."""
    for cab, corpo in _partes_mhtml(caminho):
        if _content_id(cab) != alvo:
            continue
        try:
            return base64.b64decode(corpo)
        except Exception:  # noqa: BLE001
            _LOG.exception("Foto %s ilegível no relatório", alvo)
            return None
    return None


def foto_do_paciente(registro: str, nome: str = "") -> Optional[bytes]:
    """Bytes da foto 3×4, ou ``None`` se o paciente não está no relatório.

    ``nome`` é só desempate: quando o ID não aparece, tenta pelo nome — mas um
    homônimo com a foto errada é pior que capa sem foto, então o casamento por
    nome exige coincidência exata do nome normalizado.
    """
    caminho = _arquivo(ARQ_FOTOS)
    if not os.path.exists(caminho):
        return None
    alvo_id = normalizar_id(registro)
    alvo_nome = normalizar_nome(desinverter(nome))
    if not alvo_id and not alvo_nome:
        return None
    try:
        indice = _indice_de_fotos(caminho)
        cid = (indice["id"].get(alvo_id) if alvo_id else None) or (
            indice["nome"].get(alvo_nome) if alvo_nome else None)
        if not cid:
            return None
        return _imagem_por_cid(caminho, cid)
    except Exception:  # noqa: BLE001 — capa sem foto ainda é uma capa
        _LOG.exception("Falha ao extrair a foto de %r", registro)
        return None

# ── Busca: o que a tela Capa pede ────────────────────────────────────────────

@dataclass
class Resultado:
    """O que se sabe do paciente, mais o que não se sabe.

    ``avisos`` é a parte que importa tanto quanto os dados: capa montada com
    cadastro de outro paciente é erro que só se pega olhando, e a tela mostra
    esses avisos antes de deixar imprimir.
    """
    cadastro: Cadastro = field(default_factory=Cadastro)
    prescricoes: list[Prescricao] = field(default_factory=list)
    foto: Optional[bytes] = None
    avisos: list[str] = field(default_factory=list)
    achou: bool = False
    # De onde vieram estes dados. A tela mostra: quando o banco cai e a capa
    # passa a sair dos CSV, o que está no papel pode ser o retrato de outro dia
    # — e quem assina precisa saber disso sem ter de perguntar a alguém.
    origem: str = ""


def buscar(registro: str, nome: str, nascimento: str = "") -> Resultado:
    """Monta o que houver para o paciente carregado na ficha.

    A ordem é: acha pelo ID; não achando, acha pelo nome; e o que sobrar de
    divergência entre as duas chaves vira aviso. Um paciente que não está em
    relatório nenhum devolve ``achou=False`` e a capa sai em branco para
    preenchimento — o que ainda é útil, e é honesto.
    """
    res = Resultado()
    # O BANCO primeiro, quando houver. Ele não tem janela de período — a
    # consulta é por paciente —, e é justamente a janela que fazia a capa nascer
    # sem sexo, convênio, CID e intenção para 12 481 dos 13 080 pacientes.
    # Falhando qualquer coisa (banco desligado, rede fora, paciente ausente),
    # cai nos relatórios exportados, como sempre foi.
    if _do_banco(res, registro, nome):
        return res
    # Chegou aqui com o banco CONFIGURADO quer dizer que ele não respondeu: o
    # que vem abaixo é a reserva de emergência, e a tela precisa dizer isso com
    # todas as letras. Sem o banco configurado, é o funcionamento normal de
    # quem ainda não migrou, e não há emergência nenhuma.
    # "Emergência" é o banco NÃO TER RESPONDIDO — não "o paciente não está
    # lá". Busca só por nome (sem registro) nunca acha no DW, porque a consulta
    # é por ``PatientId``; tratar isso como emergência punha o aviso "o sistema
    # não respondeu" na tela com o banco perfeitamente no ar, e aviso que mente
    # ensina a ignorar aviso.
    emergencia = _banco_configurado() and not _banco_respondeu()
    if emergencia and _do_espelho(res, registro):
        return res
    cadastro = carregar_cadastro()
    prescricoes = carregar_prescricoes()
    if not cadastro and not prescricoes:
        res.avisos.append(
            f"Sem fonte de dados: o banco não está apontado e não há "
            f"relatórios em {pasta_dados()}. O administrador aponta o sistema "
            "em Configurações → Serviço. Até lá, a capa sai em branco para "
            "preenchimento.")
        return res

    chave = normalizar_id(registro)
    alvo_nome = normalizar_nome(nome)

    if chave and chave in cadastro:
        res.cadastro = cadastro[chave]
        res.achou = True
    elif alvo_nome:
        casados = [c for c in cadastro.values()
                   if normalizar_nome(c.nome) == alvo_nome]
        if len(casados) == 1:
            res.cadastro = casados[0]
            res.achou = True
            if chave:
                res.avisos.append(
                    f"Registro {registro} não está no relatório; casei pelo "
                    f"nome, com o cadastro de ID {res.cadastro.registro}.")
        elif len(casados) > 1:
            res.avisos.append(
                f"{len(casados)} pacientes com o nome {nome} no relatório — "
                "confira o registro antes de imprimir.")

    if res.achou:
        _conferir(res, nome, nascimento)

    chave_pre = normalizar_id(res.cadastro.registro) or chave
    res.prescricoes = list(prescricoes.get(chave_pre, ()))
    if not res.prescricoes and chave_pre:
        res.avisos.append(
            AVISO_SEM_PRESCRICAO)

    if not res.achou and res.prescricoes:
        # Prescrição sem cadastro: o paciente EXISTE, mas ficou fora da janela
        # do relatório de cadastro. Sem este ramo a capa saía calada e pela
        # metade — sem convênio, contato, CID nem intenção — e quem estava na
        # frente achava que o programa tinha quebrado. Os dois relatórios saem
        # do mesmo sistema; quando as janelas de período divergem, é aqui que
        # aparece.
        _do_relatorio_de_prescricao(res, registro)
        res.avisos.append(
            f"{res.cadastro.registro or registro} tem prescrição, mas não está "
            f"no {ARQ_CADASTRO}. Sexo, nascimento, convênio, contato, médico, "
            "máquina, CID, diagnóstico e intenção saem em branco — o paciente "
            "TEM esses dados no sistema; o que falta é a linha dele nesse "
            "relatório, que sai por janela de período. Peça a exportação com o "
            "mesmo período do relatório de prescrições.")

    res.foto = foto_do_paciente(res.cadastro.registro or registro,
                                res.cadastro.nome or nome)
    res.origem = ORIGEM_RELATORIOS
    if emergencia:
        # Na FRENTE da lista: é o aviso que muda o que a pessoa faz a seguir.
        res.avisos.insert(0, aviso_de_emergencia())
    if not res.achou and not res.prescricoes:
        res.avisos.append(
            f"Paciente não encontrado nos relatórios (registro "
            f"{registro or '—'}). Preencha a capa à mão ou exporte os "
            "relatórios de novo.")
    return res


def _do_relatorio_de_prescricao(res: Resultado, registro: str) -> None:
    """Preenche do relatório de PRESCRIÇÕES o que ele também sabe.

    Não é invenção nem palpite: nome e curso são colunas do mesmo relatório,
    escritas pelo mesmo sistema. O que só existe no cadastro (convênio, contato,
    CID, diagnóstico, intenção, máquina, médico) continua vazio de propósito —
    ninguém tem de onde tirar, e a capa diz que falta.

    ``achou`` continua FALSE: o cadastro do paciente não foi encontrado, e é
    isso que a tela precisa saber para avisar.
    """
    primeira = res.prescricoes[0]
    res.cadastro.registro = (res.cadastro.registro
                             or primeira.registro_bruto.strip() or registro)
    # ``nome_bruto`` vem invertido ("Sobrenome, Nome"), como no cadastro.
    res.cadastro.nome = res.cadastro.nome or de_pessoa(primeira.nome_bruto)
    res.cadastro.curso = res.cadastro.curso or primeira.curso


def idade_dos_relatorios() -> Optional[int]:
    """Há quantos dias o relatório de cadastro foi exportado (None se não há).

    Sai da data do ARQUIVO, não do conteúdo: é a única que existe sem abrir e
    interpretar o preâmbulo, e para "isto está velho?" ela basta.
    """
    caminho = _arquivo(ARQ_CADASTRO)
    try:
        idade = datetime.now() - datetime.fromtimestamp(os.path.getmtime(caminho))
    except OSError:
        return None
    return max(0, idade.days)


def aviso_de_emergencia() -> str:
    """O recado de quem está lendo o retrato porque o sistema não respondeu."""
    dias = idade_dos_relatorios()
    if dias is None:
        quando = "e não há relatório exportado nesta estação"
    elif dias == 0:
        quando = "exportados hoje"
    elif dias == 1:
        quando = "exportados ONTEM"
    else:
        quando = f"exportados há {dias} dias"
    forte = ("  CONFIRA NO SISTEMA antes de imprimir: convênio, prescrição e "
             "diagnóstico podem ter mudado desde então."
             if dias is None or dias >= _DIAS_RELATORIO_VELHO else "")
    return (f"ÚLTIMO RECURSO: o sistema não respondeu e este paciente nunca "
            f"foi lido nesta instalação (não há espelho dele). A capa saiu dos "
            f"relatórios {quando} — é um retrato antigo, não o dado de "
            f"agora.{forte}")


def _do_espelho(res: Resultado, registro: str) -> bool:
    """A reserva de verdade: o que o banco já respondeu sobre ESTE paciente.

    Os relatórios exportados não servem de reserva depois da migração — ninguém
    vai reexportá-los, e eles envelhecem em bloco. O espelho envelhece por
    paciente: quem foi aberto hoje tem reserva de hoje, e a tela diz a idade
    DELE em vez da idade de um arquivo global.
    """
    try:
        from isocentro.banco import capa_espelho
        lido = capa_espelho.ler(registro)
    except Exception:  # noqa: BLE001
        return False
    if lido is None:
        return False
    cad, prescricoes, foto, quando = lido
    res.cadastro = cad
    res.prescricoes = list(prescricoes)
    res.foto = foto
    res.achou = True
    res.origem = ORIGEM_ESPELHO
    dias = max(0, (datetime.now() - quando).days)
    quando_texto = ("hoje" if dias == 0 else "ontem" if dias == 1
                    else f"há {dias} dias")
    forte = ("  CONFIRA NO SISTEMA antes de imprimir."
             if dias >= _DIAS_RELATORIO_VELHO else "")
    # O recado do ``capa_db.estado`` diz QUAL é a falha, e é isso que muda a
    # providência de quem lê: rede que caiu por um minuto se resolve sozinha;
    # estação sem driver ODBC nunca vai conectar e pede chamado. Antes, as duas
    # davam o mesmo "o sistema não respondeu" — e aviso que serve para tudo
    # ensina a ignorar aviso.
    try:
        from isocentro.banco import capa_db
        _, recado = capa_db.estado()
    except Exception:  # noqa: BLE001 — sem o recado o aviso ainda serve
        recado = ""
    res.avisos.insert(0, (
        f"EMERGÊNCIA: o sistema não respondeu. Esta capa saiu da última leitura "
        f"deste paciente, feita {quando_texto} "
        f"({quando.strftime('%d/%m/%Y %H:%M')}).{forte}"
        + (f"  {recado}" if recado else "")))
    if not res.prescricoes:
        res.avisos.append(AVISO_SEM_PRESCRICAO)
    return True


def _banco_respondeu() -> bool:
    """O banco está de pé agora? (não confundir com "achou o paciente")."""
    try:
        from isocentro.banco import capa_db
        return capa_db.conexao() is not None
    except Exception:  # noqa: BLE001
        return False


def _banco_configurado() -> bool:
    """O serviço já aponta o banco? Sem isso, ler os CSV é o normal."""
    try:
        from isocentro.banco import capa_db
        return capa_db.configurado()
    except Exception:  # noqa: BLE001
        return False


def _do_banco(res: Resultado, registro: str, nome: str) -> bool:
    """Tenta montar o resultado pelo data warehouse. Devolve se conseguiu.

    Só assume o caso quando achou o CADASTRO: uma consulta que devolve nada
    (banco fora do ar, paciente que não está lá) não pode impedir a leitura dos
    CSV, senão o banco teria trocado uma fonte frágil por outra.
    """
    try:
        from isocentro.banco import capa_db
    except Exception:  # noqa: BLE001
        return False
    if not capa_db.configurado():
        return False
    try:
        cad = capa_db.cadastro_do_paciente(registro)
        if cad is None:
            return False
        res.cadastro = cad
        res.achou = True
        # Prescrição é o CORPO da capa. Se a consulta falhar aqui, o resultado
        # não é "paciente sem prescrição" — é "não deu para saber", e uma capa
        # que afirma "nenhuma prescrição aprovada" para quem tem cinco é pior
        # que capa nenhuma. Desiste do banco e deixa o espelho/relatórios
        # responderem, com o aviso que eles trazem.
        res.prescricoes = capa_db.prescricoes_do_paciente(registro)
        res.foto = capa_db.foto_do_paciente(registro)
        res.origem = ORIGEM_BANCO
        # Simulação anunciada, pela mesma razão da reserva anunciada: uma capa
        # montada do arquivo gravado é indistinguível de uma capa boa depois de
        # impressa. O aviso vai em PRIMEIRO lugar, à frente até do "sem
        # prescrição" — antes de discutir o conteúdo, quem lê precisa saber que
        # aquilo não veio do sistema clínico de agora.
        try:
            from isocentro.banco import banco_local
            if banco_local.ligado():
                res.origem = ORIGEM_BANCO_LOCAL
                res.avisos.insert(0, "SIMULAÇÃO: " + banco_local.resumo())
        except Exception:  # noqa: BLE001 — sem o aviso a capa ainda sai
            _LOG.warning("Não consegui checar o banco local", exc_info=True)
        if not res.prescricoes:
            res.avisos.append(AVISO_SEM_PRESCRICAO)
        # Espelha o que acabou de chegar. Best-effort e depois de a resposta
        # estar pronta: falhar aqui não pode atrapalhar a capa de agora, e o
        # espelho é para a próxima vez que o banco não responder.
        #
        # MENOS quando veio do banco local: o espelho grava "em: agora", e é
        # essa data que a tela mostra para decidir se a reserva ainda vale. Uma
        # leitura do arquivo gravado semana passada entraria ali como espelho
        # DE HOJE — a reserva passaria a mentir a própria idade, que é a única
        # informação que ela tem além do dado. Simulação não semeia emergência.
        if res.origem != ORIGEM_BANCO_LOCAL:
            try:
                from isocentro.banco import capa_espelho
                capa_espelho.guardar(cad.registro or registro, cad,
                                     res.prescricoes, res.foto)
            except Exception:  # noqa: BLE001
                _LOG.warning("Falha ao espelhar %s", registro, exc_info=True)
        return True
    except Exception:  # noqa: BLE001 — a capa sai pelo espelho/CSV
        _LOG.exception("Falha ao ler o banco; usando a reserva.")
        # ``res`` pode ter ficado meio preenchido: zera para o próximo degrau
        # não herdar cadastro do banco com prescrição faltando.
        res.cadastro = Cadastro()
        res.achou = False
        res.prescricoes = []
        res.foto = None
        return False


def _conferir(res: Resultado, nome: str, nascimento: str) -> None:
    """Confronta o cadastro achado com o que a ficha já sabe do paciente."""
    esperado, achado = normalizar_nome(nome), normalizar_nome(res.cadastro.nome)
    if esperado and achado and esperado != achado:
        res.avisos.append(
            f"O nome no relatório ({res.cadastro.nome}) não bate com o da ficha "
            f"({nome}) — confira se é o mesmo paciente.")
    d_ficha, d_cad = ler_data(nascimento), ler_data(res.cadastro.nascimento)
    if d_ficha and d_cad and d_ficha != d_cad:
        res.avisos.append(
            f"Nascimento no relatório ({res.cadastro.nascimento}) diferente do da "
            f"ficha ({nascimento}).")


def ler_data(texto: str) -> Optional[date]:
    """Lê DD/MM/AAAA (e o AAAAMMDD que às vezes chega do DICOM)."""
    t = str(texto or "").strip()
    for fmt in ("%d/%m/%Y", "%Y%m%d", "%d/%m/%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None


def idade(nascimento: str, referencia: Optional[date] = None) -> str:
    """Idade em anos completos, ou "" quando a data não dá para ler."""
    d = ler_data(nascimento)
    if d is None:
        return ""
    hoje = referencia or date.today()
    anos = hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
    return str(anos) if anos >= 0 else ""


def data_curta(texto: str) -> str:
    """``"21/04/1947"`` → ``"21/4/1947"`` — o formato do modelo, sem zero à esquerda."""
    d = ler_data(texto)
    return f"{d.day}/{d.month}/{d.year}" if d else str(texto or "").strip()


# ── Nota de posicionamento (pasta do paciente) ───────────────────────────────
# Não vem de relatório: é o arquivo que o técnico escreve depois de montar o
# setup na TC e deixa na pasta, junto do DICOM. Quase sempre um .docx, às vezes
# um .txt. O conteúdo é uma lista de linhas curtas, e é dela que saem as duas
# metades da folha 2 da capa: as colunas de PREPARO e a caixa de ACESSÓRIOS.
#
# O vocabulário é o do serviço e está estável há anos ("CABECA PARA O GANTRY",
# "DECUBITO DORSAL", "BEXIGA CHEIA"), mas é digitado à mão: acento, cedilha e
# abreviação variam na mesma frase. Por isso o casamento é sempre feito sobre o
# texto SEM ACENTO e em maiúsculas, e o que não for reconhecido continua sendo
# acessório em vez de sumir.

_RE_PARAGRAFO = re.compile(r"</w:p>", re.IGNORECASE)
_RE_TAG = re.compile(r"<[^>]+>")

# Cada regra: (coluna do preparo, padrão, valor impresso). A ordem importa —
# "MÃOS NO TÓRAX" tem de ser lido como braço antes de qualquer regra de tórax.
# Os valores são os do relatório institucional (ver ``capa_pdf.OPCOES_PREPARO``):
# a nota é escrita à mão, a coluna sai padronizada.
_REGRAS_PREPARO: tuple[tuple[str, str, str], ...] = (
    ("BEXIGA", r"^BEXIGA\b.*\b(CHEIA)\b", "Cheia"),
    ("BEXIGA", r"^BEXIGA\b.*\b(VAZIA)\b", "Vazia"),
    ("BEXIGA", r"^BEXIGA\b.*(NAO SE APLICA|N/?A)\b", "N/A"),
    ("RETO", r"^RETO\b.*\b(VAZIO)\b", "Vazio"),
    ("RETO", r"^RETO\b.*\b(CHEIO)\b", "Cheio"),
    ("RETO", r"^RETO\b.*(NAO SE APLICA|N/?A)\b", "N/A"),
    # "MÃOS" e "BRAÇOS" sobre o tórax são a mesma instrução, e as duas grafias
    # aparecem nas notas. Só a primeira era reconhecida: "BRACOS SOBRE TORAX"
    # caía na caixa de acessórios e a linha BRAÇOS ficava vazia — o que se
    # escondia atrás do "N/A" e só apareceu quando as linhas vazias sumiram.
    # Mesmo padrão frouxo das outras linhas de BRAÇOS (``.*``): as notas
    # escrevem "SOBRE O TORAX", "SOBRE TORAX", "NO TORAX" — exigir a preposição
    # exata deixava "BRACOS SOBRE TORAX" cair na caixa de acessórios, com a
    # linha BRAÇOS vazia. Escondia-se atrás do "N/A" e só apareceu quando as
    # linhas sem valor deixaram de ser impressas.
    ("BRAÇOS", r"\b(MAOS?|BRACOS?)\b.*\bTORAX\b", "Sobre Tórax"),
    ("BRAÇOS", r"\bBRACOS? (DIR|DIREITO)\b.*\bELEVADO", "Direito elevado"),
    ("BRAÇOS", r"\bBRACOS? (ESQ|ESQUERDO)\b.*\bELEVADO", "Esquerdo elevado"),
    ("BRAÇOS", r"\bBRACOS?\b.*\b(AO LADO|AO LONGO) DO CORPO\b", "Ao lado corpo"),
    ("BRAÇOS", r"\bBRACOS?\b.*\bAFASTADOS\b", "Afastados corpo"),
    ("BRAÇOS", r"\bBRACOS?\b.*\b(ACIMA DA CABECA|AMBOS ELEVADOS)\b",
     "Ambos elevados"),
    ("PARA O GANTRY", r"^CABEC[AO]?\b.*\bGANTRY\b|^CABECA P/? GANTRY", "Cabeça"),
    ("PARA O GANTRY", r"^PES?\b.*\bGANTRY\b", "Pé"),
    ("DECÚBITO", r"^DECUBITO\b.*\bDORSAL\b", "Dorsal"),
    ("DECÚBITO", r"^DECUBITO\b.*\bVENTRAL\b", "Ventral"),
    ("DECÚBITO", r"^DECUBITO\b.*\bLATERAL DIREIT", "Lateral Dir"),
    ("DECÚBITO", r"^DECUBITO\b.*\bLATERAL ESQUERD", "Lateral Esq"),
)

# O jejum sai com as horas ("4h", "6h"), que é o que o relatório imprime — e é a
# informação que muda o que se diz ao paciente. Menção a jejum SEM as horas não
# preenche a coluna: a linha continua visível nos acessórios, e um "4h" chutado
# viraria orientação clínica inventada.
_RE_JEJUM = re.compile(r"\bJEJUM\b.*?(\d{1,2})\s*(?:H|HORAS?)\b")

# Trecho da linha que a regra "consome". O que sobrar dela ainda é acessório —
# em "DECUBITO VENTRAL NO TRAVESSEIRO" o travesseiro é um acessório de verdade e
# não pode se perder junto com o decúbito.
_RE_CONSUMIDO = {
    "PARA O GANTRY": r"^(CABEC[AO]?|PES?)\s*(PARA\s+O|P/?)?\s*GANTRY\b",
    "DECÚBITO": r"^DECUBITO\s+(DORSAL|VENTRAL|LATERAL\s+\w+)\b\s*(NO|NA|EM)?",
    "BEXIGA": r"^BEXIGA\b.*$",
    "RETO": r"^RETO\b.*$",
    # A linha que só diz onde ficam os braços vira coluna e sai da caixa. Já
    # "ÂNGULO DO BRACO -20", que é medida da rampa e não posição do paciente,
    # não começa com braço e continua sendo acessório.
    "BRAÇOS": r"^(BRACOS?|MAOS?)\b.*$",
}


def ler_nota(caminho: str) -> str:
    """Texto de uma nota de posicionamento (.docx ou .txt). "" se não der.

    O .docx é lido na mão (zip + XML), como o xlsx das fotos: uma dependência a
    mais só para varrer parágrafos de um documento de sete linhas não se paga.
    """
    ext = os.path.splitext(caminho)[1].lower()
    try:
        if ext == ".docx":
            with zipfile.ZipFile(caminho) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            # Fecha-parágrafo vira quebra de linha ANTES de tirar as tags, senão
            # o documento inteiro sairia numa linha só.
            return _desescapar(_RE_TAG.sub("", _RE_PARAGRAFO.sub("\n", xml)))
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(caminho, encoding=enc) as fh:
                    return fh.read()
            except UnicodeDecodeError:
                continue
    except Exception:  # noqa: BLE001 — capa sem nota ainda é uma capa
        _LOG.exception("Falha ao ler a nota de posicionamento %s", caminho)
    return ""


def _desescapar(s: str) -> str:
    for velho, novo in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                        ("&quot;", '"'), ("&apos;", "'")):
        s = s.replace(velho, novo)
    return s


def interpretar_notas(texto: str) -> tuple[str, dict[str, str]]:
    """Separa a nota em (acessórios, preparo), como a capa impressa os mostra.

    A nota do técnico mistura as duas coisas numa lista só. A capa as separa: o
    que é instrução de preparo vai para as colunas (bexiga, reto, gantry,
    decúbito, braços, jejum) e o resto — rampa, base, máscara, apoio, medidas —
    fica na caixa de acessórios, na ordem em que foi escrito.

    Linha não reconhecida **fica nos acessórios**: a nota é digitada à mão e um
    setup novo aparece antes de o app aprender a lê-lo. Perder a linha seria
    perder a única instrução de como deitar o paciente.
    """
    preparo: dict[str, str] = {}
    acessorios: list[str] = []
    for linha in str(texto or "").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        chave = _sem_acento(linha).upper()
        # Uma linha pode dizer duas coisas: em "DECUBITO VENTRAL NO TRAVESSEIRO"
        # o decúbito vira coluna e o travesseiro segue para os acessórios.
        resto = linha
        for coluna, padrao, valor in _REGRAS_PREPARO:
            if coluna in preparo or not re.search(padrao, chave):
                continue
            preparo[coluna] = valor
            resto = _sem_o_trecho(resto, chave, _RE_CONSUMIDO.get(coluna, ""))
        m = _RE_JEJUM.search(chave)
        if m and "JEJUM" not in preparo:
            preparo["JEJUM"] = f"{int(m.group(1))}h"
        if resto.strip():
            acessorios.append(resto.strip())
    return "\n".join(acessorios), preparo


def _sem_o_trecho(linha: str, chave: str, padrao: str) -> str:
    """Tira de ``linha`` o pedaço que ``padrao`` casou em ``chave``.

    O casamento roda sobre a chave normalizada (sem acento, maiúscula) mas o
    corte é feito na linha ORIGINAL, para o que sobrar sair impresso como o
    técnico escreveu. Os índices batem porque tirar acento não muda o número de
    caracteres — "Ã" vira "A", um por um.
    """
    if not padrao:
        return linha
    m = re.search(padrao, chave)
    if m is None:
        return linha
    return (linha[:m.start()] + linha[m.end():]).strip(" .,-—")


# ── Setups de posicionamento na pasta do paciente ────────────────────────────
# Um paciente pode ter mais de um setup: o TC7 é tratado de fêmur E de tórax, e
# cada um tem sua nota, suas fotos e seu preparo — no fêmur os braços vão sobre
# o tórax, no tórax não. São instruções de montagem diferentes, e o técnico
# precisa das duas.
#
# A pasta não diz explicitamente o que pertence a quê. Cada nota é um setup, e
# as fotos são distribuídas pelo NOME: "<paciente> FEMUR FOTO.JPG" tem
# "FEMUR", que é o nome da nota `FEMUR.docx`. Quando o nome não diz nada
# ("<paciente> 1/2/4/5"), a foto vai para o primeiro setup e quem está
# montando a ficha redistribui na tela — adivinhar qual foto é da máscara de
# radiocirurgia e qual é da rampa de tórax não é trabalho de programa.

EXT_FOTOS = (".jpg", ".jpeg", ".png", ".bmp")
EXT_NOTAS = (".docx", ".txt")

# Arquivos que o PRÓPRIO app grava e que não são entrada de nada.
#
# Duas famílias. Na pasta da simulação, a nota legível e o cadastro — reinterpretá
# -los pôe o cabeçalho do próprio arquivo dentro da capa. Na pasta do paciente, os
# PNGs do registro versionado (``registro_json``): cortes, DVH e DRR. Estes são o
# caso mais grave, porque são **imagens** — sem excluí-los, a capa de qualquer
# paciente cuja ficha já foi gerada mostraria os cortes de dose nos quadros de
# foto de posicionamento, e a busca pela simulação nunca aconteceria, já que a
# pasta "tinha fotos".
# Os nomes vêm do ``simulacao`` (import local para não fechar o ciclo), com
# literais só como reserva se o módulo não puder ser carregado.
def _nomes_do_cadastro() -> frozenset:
    try:
        from isocentro.interface import simulacao
        return frozenset({simulacao.ARQ_NOTA.upper(),
                          simulacao.ARQ_CADASTRO.upper()})
    except Exception:  # noqa: BLE001
        return frozenset({"POSICIONAMENTO.TXT", "SIMULACAO.JSON"})
_PREFIXOS_GERADOS = ("CORTES_", "DVH_", "DRR_", "PREVIA_", "FICHA_", "ALTA_",
                     "ARQUIVOS_")


def _gerado_pelo_app(nome: str) -> bool:
    """O arquivo é saída do próprio programa, e não algo que alguém pôs ali?"""
    alto = nome.upper()
    return alto in _nomes_do_cadastro() or alto.startswith(_PREFIXOS_GERADOS)

# Palavras que aparecem em quase todo nome de arquivo e não distinguem setup
# nenhum — usá-las no casamento faria "FOTO" casar com tudo.
_TOKENS_VAZIOS = {"FOTO", "FOTOS", "SETUP", "POSICIONAMENTO", "IMG", "IMAGE",
                  "DSC", "WHATSAPP", "DE", "DA", "DO", "E", "COM"}


@dataclass
class Setup:
    """Um jeito de posicionar o paciente: nota, fotos e preparo."""
    nome: str = ""
    fotos: list[bytes] = field(default_factory=list)
    acessorios: str = ""
    preparo: dict[str, str] = field(default_factory=dict)
    arquivo: str = ""        # a nota de onde ele saiu, para a tela dizer


def _tokens_do_setup(nome: str) -> set[str]:
    """Palavras do nome da nota que valem para casar fotos.

    ``"MAMA VAC = LOCK.docx"`` → ``{"MAMA", "VAC", "LOCK"}``. Palavras de uma
    letra e as genéricas ficam de fora.
    """
    brutos = re.split(r"[^A-Z0-9]+", normalizar_nome(nome))
    return {t for t in brutos if len(t) > 2 and t not in _TOKENS_VAZIOS}


def identidade_da_pasta(pasta: str) -> dict:
    """Quem é o paciente desta pasta, sem carregar o plano.

    A Capa precisa saber de quem é a pasta para procurar o cadastro nos
    relatórios — e precisa disso ANTES de existir qualquer plano na bancada,
    porque quem chega da tomografia não tem plano nenhum. Ler o caso inteiro só
    para descobrir um nome custa segundos e traz TC, dose e estruturas que esta
    tela não usa.

    Três fontes, da mais barata e exata para a mais cara:

    1. o **cadastro de simulação** gravado ao sair da tomografia;
    2. a **ficha anterior** arquivada na pasta (JSON solto ou dentro do zip);
    3. o **primeiro DICOM legível** — qualquer objeto traz a demografia.

    Devolve ``{"nome", "registro", "nascimento"}``; campos que não apareceram
    voltam vazios, nunca inventados.
    """
    vazio = {"nome": "", "registro": "", "nascimento": ""}
    if not pasta or not os.path.isdir(pasta):
        return vazio

    # 1. Cadastro da simulação — é dado, não texto a interpretar.
    try:
        from isocentro.interface import simulacao
        sim = simulacao.carregar(pasta)
        if sim is not None:
            achado = {"nome": str(getattr(sim, "nome", "") or ""),
                      "registro": str(getattr(sim, "registro", "") or ""),
                      "nascimento": str(getattr(sim, "nascimento", "") or "")}
            # Só vale se identificar ALGUÉM. Um SIMULACAO.json truncado ou sem
            # paciente bloqueava as outras duas fontes, e a tela dizia "sem
            # DICOM" numa pasta cheia de DICOM.
            if achado["nome"] or achado["registro"]:
                return achado
    except Exception:  # noqa: BLE001 — fonte acessória
        pass

    # 2. Ficha anterior arquivada na pasta.
    try:
        from isocentro.dados import registro_json
        reg = registro_json.registro_na_pasta(pasta)
        if reg:
            pac = reg.get("paciente") or {}
            if pac.get("nome") or pac.get("registro"):
                return {"nome": str(pac.get("nome", "") or ""),
                        "registro": str(pac.get("registro", "") or ""),
                        "nascimento": str(pac.get("nascimento", "") or "")}
    except Exception:  # noqa: BLE001
        pass

    # 3. O primeiro DICOM que abrir. ``stop_before_pixels`` porque a demografia
    # está no cabeçalho: ler os pixels de uma TC inteira para pegar um nome
    # seria trocar segundos por nada.
    try:
        import pydicom

        from isocentro.dicom import dicom_rt
        for raiz, _dirs, arquivos in os.walk(pasta):
            for nome_arq in sorted(arquivos):
                if not nome_arq.lower().endswith(".dcm"):
                    continue
                try:
                    ds = pydicom.dcmread(os.path.join(raiz, nome_arq),
                                         stop_before_pixels=True, force=True)
                except Exception:  # noqa: BLE001 — arquivo torto: tenta o próximo
                    continue
                d = dicom_rt.dados_paciente(ds)
                if d.get("nome") or d.get("registro"):
                    return {"nome": d.get("nome", ""),
                            "registro": d.get("registro", ""),
                            "nascimento": d.get("nascimento", "")}
    except Exception:  # noqa: BLE001
        _LOG.exception("Capa: falha ao identificar a pasta %s", pasta)
    return vazio


def setups_da_pasta(pasta: str) -> list[Setup]:
    """Os setups de posicionamento que a pasta contém.

    Se houver um cadastro de simulação (``SIMULACAO.json``, gravado pela tela de
    Simulação), é ele que vale: ali os setups já vêm estruturados, e não há
    nada a interpretar. É o fim da adivinhação — a nota deixa de ser texto livre
    que o programa tenta entender e passa a ser dado.

    Sem cadastro, o caminho antigo: uma nota ``.docx``/``.txt`` = um setup, e as
    fotos distribuídas pelo nome. Continua valendo para tudo que foi simulado
    antes desta tela existir.
    """
    if not pasta or not os.path.isdir(pasta):
        return []
    cadastrados = _setups_do_cadastro(pasta)
    if cadastrados is not None:
        return cadastrados
    try:
        nomes = sorted(os.listdir(pasta))
    except OSError:
        return []

    # O que o app gerou fica de fora das duas listas — ver ``_gerado_pelo_app``.
    nomes = [n for n in nomes if not _gerado_pelo_app(n)]
    fotos = [n for n in nomes if n.lower().endswith(EXT_FOTOS)]
    notas = [n for n in nomes if n.lower().endswith(EXT_NOTAS)]
    if not notas:
        imagens = [b for b in (_bytes(pasta, f) for f in fotos) if b]
        # Pasta sem nota E sem foto não tem setup nenhum. Devolver um setup
        # vazio faria quem chama pensar que achou alguma coisa — e era o que
        # desligava a ponte para o cadastro de simulação (ver
        # ``capa.PainelCapa.carregar_da_pasta``), que só procura quando a pasta
        # do paciente não deu nada.
        return [Setup(fotos=imagens)] if imagens else []

    setups = []
    for nota in notas:
        acessorios, preparo = interpretar_notas(ler_nota(os.path.join(pasta, nota)))
        setups.append(Setup(nome=os.path.splitext(nota)[0], acessorios=acessorios,
                            preparo=preparo, arquivo=nota))

    for foto in fotos:
        dono = _setup_da_foto(foto, setups)
        dados = _bytes(pasta, foto)
        if dados:
            dono.fotos.append(dados)
    return setups


def _setups_do_cadastro(pasta: str) -> Optional[list[Setup]]:
    """Setups do ``SIMULACAO.json``, ou ``None`` se a pasta não tem cadastro.

    O import é local de propósito: ``simulacao`` importa este módulo, e no topo
    o ciclo travaria a carga dos dois.
    """
    try:
        from isocentro.interface import simulacao

        sim = simulacao.carregar(pasta)
    except Exception:  # noqa: BLE001 — cai no caminho antigo
        _LOG.exception("Falha ao ler o cadastro de simulação em %s", pasta)
        return None
    return sim.setups if sim is not None and sim.setups else None


def simulacao_do_paciente(nome: str, registro: str = "") -> list[Setup]:
    """Setups da simulação cadastrada para o paciente, onde ela estiver.

    A pasta do DICOM e a pasta da simulação são lugares diferentes — o
    dosimetrista cadastra ao sair da TC, muito antes de existir plano. Esta é a
    ponte: a Capa pergunta pelo paciente e recebe o que foi registrado na
    tomografia, sem ninguém ter de copiar arquivo de um lugar para o outro.
    """
    try:
        from isocentro.interface import simulacao

        pasta = simulacao.procurar(nome, registro)
    except Exception:  # noqa: BLE001
        _LOG.exception("Falha ao procurar a simulação de %r", nome)
        return []
    return setups_da_pasta(pasta) if pasta else []


def _setup_da_foto(foto: str, setups: list[Setup]) -> Setup:
    """A qual setup a foto pertence, pelo nome. Sem pista, vai para o primeiro.

    Vence o setup com MAIS palavras em comum: "MAMA VAC LOCK" ganha de "MAMA"
    numa foto que traz as três.
    """
    chave = _tokens_do_setup(foto)
    melhor, pontos = setups[0], 0
    for s in setups:
        n = len(_tokens_do_setup(s.nome) & chave)
        if n > pontos:
            melhor, pontos = s, n
    return melhor


def _bytes(pasta: str, nome: str) -> Optional[bytes]:
    try:
        with open(os.path.join(pasta, nome), "rb") as fh:
            return fh.read()
    except OSError:
        _LOG.exception("Falha ao ler %s", nome)
        return None


# ── Lista de pacientes: a busca da tela de Simulação ──────────────────────

@dataclass
class PacienteRef:
    """O mínimo para escolher um paciente numa lista: nome, ID e nascimento."""
    registro: str = ""
    nome: str = ""
    nascimento: str = ""

    def rotulo(self) -> str:
        """``"ANTONIO CARLOS DE SOUZA  ·  1111111AAA  ·  21/4/1947"``."""
        partes = [self.nome, self.registro, data_curta(self.nascimento)]
        return "  ·  ".join(p for p in partes if p)

    def casa(self, termo: str) -> bool:
        """O termo digitado bate com este paciente?

        Casa por PEDAÇO de nome e por pedaço de ID, sem acento e sem caixa: quem
        procura digita "souza" ou os últimos dígitos do registro, não o nome
        completo com a grafia exata do cadastro.
        """
        if not str(termo or "").strip():
            return True
        # Dois crivos, porque nome e ID se normalizam diferente: quem cola
        # "9000004-CEL" ou "9000004 CEL" tem de achar tanto quanto quem digita
        # o nome. Comparar o termo já normalizado como NOME contra o ID
        # normalizado nunca casava, porque um mantém espaços e o outro não.
        por_nome = normalizar_nome(termo)
        por_id = normalizar_id(termo)
        # ``bool(...)`` porque o ``and`` propaga o operando FALSO, não False:
        # com ``por_nome`` vazio isto devolvia a STRING "" — falsy, então
        # funcionava em ``if`` e em compreensão, mas a função anotada como
        # ``bool`` não devolvia bool. Quem comparasse com ``is False`` ou
        # serializasse o resultado pegaria a diferença do jeito ruim.
        return bool((por_nome and por_nome in normalizar_nome(self.nome))
                    or (por_id and por_id in normalizar_id(self.registro)))


def pacientes() -> list[PacienteRef]:
    """Todos os pacientes que os relatórios conhecem, em ordem de nome.

    Duas fontes, e as duas fazem falta: o de **cadastro** é o único que traz a
    data de nascimento, mas cobre só quem está em tratamento no período
    exportado (algumas centenas); o de **prescrições** cobre o histórico inteiro
    (milhares), com nome e ID. Quem chega da tomografia muitas vezes ainda não
    está no primeiro — então a lista é a união, com a DDN preenchida onde existe.
    """
    # O BANCO primeiro, quando apontado. Depois da migração ninguém reexporta
    # os CSV: sem este desvio, a busca da tela ficaria VAZIA — e a porta de
    # quem chega da tomografia é justamente essa lista.
    try:
        from isocentro.banco import capa_db
        if capa_db.configurado():
            do_banco = capa_db.pacientes()
            if do_banco:
                return do_banco
            # Vazio aqui é banco fora do ar ou consulta que falhou; os CSV, se
            # existirem, ainda deixam escolher alguém.
    except Exception:  # noqa: BLE001
        _LOG.exception("Falha ao listar pacientes pelo banco; usando os CSV.")

    cadastro = carregar_cadastro()
    out: dict[str, PacienteRef] = {
        chave: PacienteRef(registro=c.registro, nome=c.nome,
                           nascimento=c.nascimento)
        for chave, c in cadastro.items()
    }
    for chave, lista in carregar_prescricoes().items():
        if chave in out or not lista:
            continue
        # O relatório de prescrições repete o nome em toda linha; a primeira
        # basta, e vem invertida como no cadastro.
        out[chave] = PacienteRef(registro=lista[0].registro_bruto,
                                 nome=de_pessoa(lista[0].nome_bruto))
    return sorted(out.values(), key=lambda p: normalizar_nome(p.nome))
