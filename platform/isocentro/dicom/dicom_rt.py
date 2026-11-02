"""Leitura dos objetos DICOM-RT (TC, RP, RS, RD) para a ficha técnica.

Cada função recebe um ``pydicom.Dataset`` já carregado e devolve um
dicionário com os campos relevantes para a ficha. As funções são tolerantes
a tags ausentes — sempre usam ``getattr``/``.get`` com valor padrão.
"""

from __future__ import annotations

import logging as _logging
import math as _math
import statistics as _statistics
import unicodedata
from typing import Any

import pydicom
from isocentro.dominio import constantes
# A função, não o módulo: duas funções daqui já têm um parâmetro chamado
# ``nomes`` (``unificar_grafias``, ``ordem_alfabetica``),
# e ``import nomes`` ficaria sombreado dentro delas — quem viesse usá-lo ali
# teria um AttributeError sem explicação.
from isocentro.dados.nomes import como_nome_proprio
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue

_LOG = _logging.getLogger(__name__)

# Modalidades DICOM dos objetos de interesse.
MODALIDADES = {
    "CT": "TC",
    "RTPLAN": "RP",
    "RTSTRUCT": "RS",
    "RTDOSE": "RD",
    "RTIMAGE": "RI",            # DRR de setup (portais) — páginas de conferência
    "MOTIONMTPROTOCOL": "MP",   # protocolo de gating da Varian (amplitude/fase)
}

# ── Constantes físicas ───────────────────────────────────────────────────────
_SAD_MM     = 1000.0   # Source-to-Axis Distance padrão Varian/Elekta (mm)
_SSD_MIN_CM = 50.0     # Limites de sanidade para o SSD calculado (cm)
_SSD_MAX_CM = 150.0
_HU_PELE    = -150.0   # Limiar HU tecido mole / ar para raycast na TC


def soltar_cache_pixels(ds) -> None:
    """Invalida o ``pixel_array`` decodificado que o pydicom cacheia no dataset.

    Mantém o ``PixelData`` cru — um acesso futuro re-decodifica — e solta só a
    cópia numpy grande (uma grade de dose ou um corte de TC) que ficaria presa
    no objeto. Num paciente multi-plano essa cópia é de centenas de MB por RD.

    O pydicom (3.0.2) não expõe API pública para isso, então mexe no atributo
    privado ``_pixel_array``. Se uma versão futura o renomear, o clear viraria
    um no-op EM SILÊNCIO — de volta ao vazamento que isto corrige. O aviso no
    log torna essa quebra visível; ``tests/test_pixel_cache.py`` a transforma em
    teste que falha na hora de subir a versão do pydicom.
    """
    if hasattr(ds, "_pixel_array"):
        ds._pixel_array = None
        if hasattr(ds, "_pixel_id"):     # auxiliar do cache; zera junto
            ds._pixel_id = None
    else:
        _LOG.warning(
            "pydicom %s: Dataset sem '_pixel_array' — o cache de pixels não foi "
            "solto e a memória pode vazar; reveja dicom_rt.soltar_cache_pixels().",
            getattr(pydicom, "__version__", "?"),
        )


def _formatar_nome(valor: Any) -> str:
    """Converte um PersonName DICOM em nome na ordem natural (nome sobrenome).

    O DICOM armazena ``Família^Nome^Meio`` (sobrenome primeiro). A ficha usa a
    ordem natural brasileira, então reordenamos para ``Nome Meio Família``.

    A GRAFIA sai daqui canônica (``como_nome_proprio``): cada TPS grava
    como quer — o mesmo paciente vem "SANDRA CABRAL DA LUZ" de um e "Sandra
    Cabral da Luz" de outro —, e antes disso a lista de fichas recentes exibia
    as duas formas lado a lado, como se fossem dados de origens diferentes.
    """
    if not valor:
        return ""
    familia = str(getattr(valor, "family_name", "") or "").strip()
    nome = str(getattr(valor, "given_name", "") or "").strip()
    meio = str(getattr(valor, "middle_name", "") or "").strip()
    if familia or nome:
        # Alguns sistemas repetem o sobrenome dentro do componente "nome"
        # (ex.: 'Monteiro^Paula Monteiro Aragao'); nesse caso não duplicamos.
        if familia and familia.lower() in nome.lower():
            completo = nome
        else:
            completo = " ".join(p for p in (nome, meio, familia) if p)
    else:
        completo = str(valor).replace("^", " ")
    return como_nome_proprio(" ".join(completo.split()))


def _primeiro_nome(valor: Any) -> str:
    """Formata o primeiro nome de um campo que pode ser multivalorado."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, MultiValue):
        valor = valor[0] if len(valor) else ""
    return _formatar_nome(valor)


# ── Equipe: casar o nome do DICOM com a pessoa ──────────────────────────────
# As LISTAS (quem é físico, quem é médico, em que unidade atende) moram em
# ``dados/equipe.py`` desde a R-58 (22/10/2026); aqui fica só o algoritmo de
# casar grafias. Quem lê o plano recebe as listas por parâmetro OBRIGATÓRIO:
# com padrão vazio, esquecer de passá-las daria um físico em branco na ficha
# sem erro nenhum — assim dá TypeError na primeira execução.


def _mais_completo(a: str, b: str) -> str:
    """Entre duas grafias da MESMA pessoa, a que traz mais nome.

    Mais tokens ganha ("Lais Toscano Mayer João" sobre "Lais Toscano Mayer"); empate
    de tokens vai no texto mais longo ("Ana Fátima de Paula Brandao Albuquerque"
    sobre "Ana Fatima Albuquerque"). Nome incompleto na ficha é nome que o médico
    vai ter de corrigir à mão.
    """
    ta, tb = _tokens(a), _tokens(b)
    if len(ta) != len(tb):
        return a if len(ta) > len(tb) else b
    return a if len(a) >= len(b) else b


def unificar_grafias(nomes) -> list:
    """Uma entrada por PESSOA, com a grafia mais completa de cada uma.

    A lista canônica e o cadastro de cada serviço escrevem a mesma pessoa de
    jeitos diferentes; juntando as duas, ela aparecia duas vezes no combo.
    Quem decide se são a mesma pessoa é ``mesma_pessoa`` (primeiro nome e ao
    menos dois tokens), e quem fica é ``_mais_completo``.
    """
    escolhidos: list = []
    for nome in nomes:
        igual = mesma_pessoa(nome, escolhidos)
        if not igual:
            escolhidos.append(nome)
            continue
        vence = _mais_completo(nome, igual)
        if vence != igual:
            escolhidos[escolhidos.index(igual)] = vence
    return escolhidos


def ordem_alfabetica(nomes) -> list:
    """Nomes em ordem alfabética, ignorando acento e caixa.

    Toda lista de equipe cresce por ACRÉSCIMO — nome novo vai para o fim, aqui e
    no arquivo de cada instalação —, então a ordem do arquivo não serve para
    exibir. Ordenar na leitura deixa Configurações → Equipe e os combos da ficha
    sempre alfabéticos, sem depender de o arquivo estar arrumado.

    Sem tirar o acento a comparação é por code point e "Thaís" iria depois de
    "Z"; ``_normalizar`` é o mesmo critério usado para casar nome do DICOM.
    """
    return sorted(nomes, key=_normalizar)


# Conectores que não distinguem pessoas (sobrenomes compostos).
_CONECTORES = {"de", "da", "do", "das", "dos", "e", "di", "del", "la", "e."}


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e sem pontuação, para comparar nomes."""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpo = "".join(c if c.isalnum() or c.isspace() else " " for c in sem_acento)
    return " ".join(limpo.lower().split())


def _tokens(nome: str) -> list[str]:
    """Tokens significativos do nome (sem acentos e sem conectores)."""
    return [t for t in _normalizar(nome).split() if t not in _CONECTORES]


def _casar_nome(nome: Any, candidatos) -> str:
    """Retorna o nome canônico de ``candidatos`` que corresponde a ``nome``
    (um PersonName/str vindo do DICOM), ou "" se nenhum corresponder.

    Exige que o primeiro nome (given name) bata e escolhe o candidato com
    maior sobreposição de tokens, evitando falsos positivos por conectores
    ("de", "da") ou por um sobrenome coincidente.
    """
    alvo = _tokens(_formatar_nome(nome))
    if not alvo:
        return ""
    primeiro = alvo[0]
    melhor, melhor_score = "", 0
    for cand in candidatos:
        cand_tokens = set(_tokens(cand))
        if primeiro not in cand_tokens:
            continue
        score = len(set(alvo) & cand_tokens)
        # Exige casamento forte: ao menos dois tokens em comum (nome + sobrenome),
        # exceto quando o nome do DICOM ou o candidato tem um único token — assim
        # "Nathalia Ramalho Ogawa" (médica) não casa com "Nathalia Bittencourt" (física).
        if score < 2 and len(alvo) > 1 and len(cand_tokens) > 1:
            continue
        if score > melhor_score:
            melhor, melhor_score = cand, score
    return melhor


def mesma_pessoa(nome: str, candidatos) -> str:
    """O nome de ``candidatos`` que é A MESMA PESSOA que ``nome``, ou "".

    Serve para reconciliar DUAS listas de pessoas — o cadastro do serviço contra
    a lista canônica, onde a mesma médica aparece como "Ana Fatima Albuquerque" e
    "Ana Fátima de Paula Brandao Albuquerque".

    Exige primeiro nome igual e ao menos DOIS tokens em comum, sempre. É mais
    estrito que ``_casar_nome``, que aceita um token só para resolver login e
    primeiro nome vindos do DICOM ("adriano"): aqui um falso positivo faz sumir
    um nome do cadastro, e é melhor deixar dois nomes parecidos na lista do que
    engolir uma pessoa de verdade.
    """
    alvo = _tokens(nome)
    if len(set(alvo)) < 2:
        return ""
    melhor, melhor_score = "", 1
    for cand in candidatos:
        cand_tokens = set(_tokens(cand))
        if alvo[0] not in cand_tokens:
            continue
        score = len(set(alvo) & cand_tokens)
        if score > melhor_score:
            melhor, melhor_score = cand, score
    return melhor


def _selecionar_fisico(operators: Any = "", reviewer: Any = "", *,
                       fisicos, medicos) -> str:
    """Nome do físico do plano.

    ``OperatorsName`` (0008,1070) é quem elaborou o plano no TPS — nos RTPLAN do
    serviço é sempre o físico —, então tem PRIORIDADE. ``ReviewerName`` (300E,0008)
    é quem APROVOU e às vezes é o médico, por isso vem depois e só entra se casar
    com a lista de físicos.

    1. casa ``OperatorsName`` e depois ``ReviewerName`` contra a lista canônica;
    2. se nenhum casar, usa o ``OperatorsName`` CRU — desde que não seja um médico
       conhecido —, pois ele é comprovadamente o físico (cobre físicos ainda fora
       da lista, ex.: um residente/novo contratado).
    Retorna "" se não houver candidato utilizável.
    """
    def _entradas(v):
        if v is None or v == "":
            return []
        return list(v) if isinstance(v, MultiValue) else [v]

    # OperatorsName é autoritativo: esgota-o antes de olhar o revisor. Casa com a
    # lista canônica; se não estiver nela, usa o nome cru — desde que pareça um
    # NOME (≥2 tokens) e não seja um médico conhecido. O piso de 2 tokens rejeita
    # login/iniciais (ex.: "QA") que alguns TPS gravam aí, deixando o revisor-
    # físico entrar; ainda cobre o físico fora da lista (ex.: "Plinio Henrique …").
    for entrada in _entradas(operators):
        fisico = _casar_nome(entrada, fisicos)
        if fisico:
            return fisico
        if len(_tokens(_formatar_nome(entrada))) >= 2 \
                and not _casar_nome(entrada, medicos):
            return _formatar_nome(entrada)
    # Sem OperatorsName utilizável: o revisor só entra se for um físico conhecido
    # (às vezes é o médico que aprovou o plano).
    for entrada in _entradas(reviewer):
        fisico = _casar_nome(entrada, fisicos)
        if fisico:
            return fisico
    return ""


def _selecionar_medico(valor: Any, *, medicos) -> str:
    """Casa o nome do médico (PhysiciansOfRecord) contra a lista canônica;
    se não reconhecer, devolve o nome formatado como veio no DICOM."""
    entradas = valor if isinstance(valor, MultiValue) else [valor]
    for entrada in entradas:
        canonico = _casar_nome(entrada, medicos)
        if canonico:
            return canonico
    return _primeiro_nome(valor)


def _formatar_data(valor: Any) -> str:
    """Converte uma data DICOM (YYYYMMDD) em DD/MM/YYYY."""
    if not valor or len(str(valor)) < 8:
        return str(valor or "")
    s = str(valor)
    return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"


def identificar(ds: Dataset) -> str:
    """Retorna o código (TC/RP/RS/RD) a partir da modalidade do dataset."""
    return MODALIDADES.get(getattr(ds, "Modality", ""), getattr(ds, "Modality", "?"))


def dados_paciente(ds: Dataset) -> dict:
    """Demografia do paciente — presente em qualquer objeto DICOM."""
    return {
        "nome": _formatar_nome(getattr(ds, "PatientName", "")),
        "registro": str(getattr(ds, "PatientID", "") or ""),
        "nascimento": _formatar_data(getattr(ds, "PatientBirthDate", "")),
        "sexo": str(getattr(ds, "PatientSex", "") or ""),
    }


def _drr_eh_setup(ds: Dataset) -> bool:
    """True só para o DRR de conferência de SETUP: o rótulo precisa conter
    'PORTAL' (ex.: 'PORTAL 0-DRR'), nunca os DRRs por feixe ('7 G45-DRR')."""
    return "PORTAL" in str(getattr(ds, "RTImageLabel", "")).upper()


def _nome_do_feixe_referenciado(ds, planos) -> str:
    """``BeamName`` do feixe que este RT Image referencia (ou "" se não casar).

    O casamento é (plano, feixe), como em ``selecionar_drrs_setup``. Quando o
    RT Image não diz o UID do plano, o número do feixe ainda decide — é a mesma
    tolerância que a seleção dos portais já pratica, e sem ela um acervo que
    perdeu a referência do plano ficaria com o nome cortado à toa.

    Mas aí só valem feixes de **SETUP**: número de feixe REINICIA a cada plano,
    então, sem o UID, o primeiro plano com aquele número vence — e um feixe de
    TRATAMENTO batizaria o portal com o nome de um campo que não é ele. Com o
    UID casado não há essa dúvida: a imagem aponta para aquele feixe.
    """
    if not planos:
        return ""
    puid, bn = _ri_plano_beam(ds)
    if bn is None:
        return ""
    for p in planos:
        casou_plano = bool(puid and sop_uid(p) and puid == sop_uid(p))
        if puid and sop_uid(p) and not casou_plano:
            continue
        for b in getattr(p, "BeamSequence", []):
            n = getattr(b, "BeamNumber", None)
            if n is None or int(n) != bn:
                continue
            if not casou_plano and str(
                    getattr(b, "TreatmentDeliveryType", "")).upper() != "SETUP":
                continue
            for campo in ("BeamName", "BeamDescription"):
                valor = str(getattr(b, campo, "") or "").strip()
                if valor:
                    return valor
    return ""


def rotulo_drr_setup(ds, planos: list | None = None) -> str:
    """Nome do portal — do RT PLAN quando ele estiver à mão; senão, da imagem.

    O ``RTImageLabel`` é VR ``SH``: **dezesseis caracteres**, contando o sufixo
    "-DRR" que o Eclipse acrescenta. Sobram doze para o nome, e no acervo isso
    corta nomes de verdade — o TC15 tem ``'PORTAL MAMA -DRR'`` para o feixe
    chamado ``PORTAL MAMA TG`` e ``'PORTAL FSC 3-DRR'`` para ``PORTAL FSC 345``.
    Quem confere o portal na sala procura o nome que aparece no console, e
    "PORTAL FSC 3" é um nome que não existe lá.

    O nome inteiro está no ``BeamName`` do feixe de SETUP que a imagem
    referencia (VR ``LO``, 64 caracteres). Sem os planos — ou sem casar o feixe
    — volta ao rótulo da imagem: cortado é melhor que vazio.

    Ex.: 'PORTAL 0-DRR' → 'PORTAL 0'; 'PORTAL FSC 3-DRR' → 'PORTAL FSC 345'.
    """
    nome = _nome_do_feixe_referenciado(ds, planos)
    if nome:
        return nome
    import re
    lbl = str(getattr(ds, "RTImageLabel", "") or "").strip()
    return re.sub(r"\s*-?\s*DRR\s*$", "", lbl, flags=re.IGNORECASE).strip()


def _feixes_setup(planos: list) -> set:
    """``{(plano_uid, beam_number)}`` dos feixes de SETUP (posicionamento) dos
    RTPLANs — são eles que geram os portais de conferência."""
    setup = set()
    for p in planos or []:
        uid = sop_uid(p)
        for b in getattr(p, "BeamSequence", []):
            if str(getattr(b, "TreatmentDeliveryType", "")).upper() == "SETUP":
                n = getattr(b, "BeamNumber", None)
                if n is not None:
                    setup.add((uid, int(n)))
    return setup


def _ri_plano_beam(ds) -> tuple:
    """(plano_uid, beam_number) que o RT Image referencia."""
    seq = getattr(ds, "ReferencedRTPlanSequence", None)
    puid = str(getattr(seq[0], "ReferencedSOPInstanceUID", "") or "") if seq else ""
    bn = getattr(ds, "ReferencedBeamNumber", None)
    return (puid, int(bn)) if bn is not None else (puid, None)


def _eh_portal_zero(ds) -> bool:
    """True para o portal 0 (AP, gantry ≈ 0), que abre a sequência de DRRs."""
    import re
    g = getattr(ds, "GantryAngle", None)
    if g is not None:
        try:
            return abs((float(g) + 180) % 360 - 180) < 1.0
        except (TypeError, ValueError):
            pass
    return bool(re.match(r"\s*portal\s*0\b",
                         str(getattr(ds, "RTImageLabel", "")), re.IGNORECASE))


def selecionar_drrs_setup(ris: list, planos: list | None = None) -> list:
    """DRRs de conferência = RT Images que referenciam os feixes de SETUP do plano.

    Robusto para qualquer geometria (mama+FSC tem vários portais em ângulos
    quaisquer, não só AP/perfil). Os DRRs por feixe de tratamento ficam de fora.
    Sem os planos (ou sem casar nenhum feixe), cai no rótulo 'PORTAL'. O portal 0
    (AP) vem sempre primeiro; os demais mantêm a ordem de entrada."""
    setup = _feixes_setup(planos or [])
    sel = [d for d in ris if _ri_plano_beam(d) in setup] if setup else []
    if not sel:
        sel = [d for d in ris if _drr_eh_setup(d)]
    return sorted(sel, key=lambda d: 0 if _eh_portal_zero(d) else 1)  # estável


def drr_geometria(ds: Dataset) -> dict:
    """Pixels e geometria de um DRR para renderização com retículo no isocentro.

    O isocentro (0,0) do plano do receptor cai no pixel dado por ``RTImagePosition``
    (canto sup. esq., em mm) e ``ImagePlanePixelSpacing`` ([linha, coluna]).
    """
    px = ds.pixel_array
    rows, cols = px.shape[:2]
    esp = [float(v) for v in getattr(ds, "ImagePlanePixelSpacing", [1.0, 1.0])]
    esp_lin, esp_col = esp[0], esp[1]
    pos = getattr(ds, "RTImagePosition", None)
    if pos is not None and len(pos) == 2 and esp_lin and esp_col:
        col_iso = -float(pos[0]) / esp_col      # x=0 → coluna
        lin_iso = float(pos[1]) / esp_lin       # y=0 → linha (y cresce p/ cima)
    else:                                       # sem geometria: centro da imagem
        col_iso, lin_iso = cols / 2.0, rows / 2.0
    return {
        "pixels": px,
        "col_iso": col_iso, "lin_iso": lin_iso,
        "esp_lin": esp_lin, "esp_col": esp_col,
        "label": str(getattr(ds, "RTImageLabel", "")),
    }


def parse_ct(ds: Dataset) -> dict:
    """Dados do exame de TC."""
    return {
        "paciente": dados_paciente(ds),
        "instituicao": str(getattr(ds, "InstitutionName", "") or ""),
        "data_estudo": _formatar_data(getattr(ds, "StudyDate", "")),
        "descricao_estudo": str(getattr(ds, "StudyDescription", "") or ""),
        "espessura_corte": getattr(ds, "SliceThickness", None),
    }


def _tecnica_do_feixe(beam: Dataset) -> str:
    """Infere a técnica de tratamento a partir do feixe do RTPLAN."""
    beam_type = str(getattr(beam, "BeamType", "")).upper()
    radiacao = str(getattr(beam, "RadiationType", "")).upper()
    cps = getattr(beam, "ControlPointSequence", [])
    if radiacao == "ELECTRON":
        return "Elétrons"
    if beam_type == "DYNAMIC":
        # Gantry varia entre control points -> arco (VMAT); caso contrário, IMRT dinâmico.
        angulos = {getattr(cp, "GantryAngle", None) for cp in cps if hasattr(cp, "GantryAngle")}
        return "VMAT" if len(angulos) > 1 else "IMRT"
    return "3D Conformacional (3D-CRT)"


def _cm(valor_mm: Any) -> float | None:
    """Converte milímetros (DICOM) em centímetros, com 1 casa."""
    return round(float(valor_mm) / 10.0, 1) if valor_mm is not None else None


def _troca_sinal(v: float | None) -> float | None:
    """Inverte o sinal preservando None — e sem devolver -0.0."""
    return None if v is None else (-v if v else 0.0)


def _mordentes(cp0: Dataset) -> dict:
    """Posições dos mordentes (X1/X2/Y1/Y2) em cm, como o console mostra.

    O DICOM traz as posições assinadas no eixo do colimador (IEC 61217): X1/Y1
    ficam do lado negativo e X2/Y2 do positivo. O console mostra a ABERTURA de
    cada mordente a partir do eixo central, então X1/Y1 saem com o sinal
    trocado e X2/Y2 como estão. Um mordente que ULTRAPASSA o eixo central
    (over-travel) fica NEGATIVO na ficha, nos dois casos: era o que o ``abs()``
    de antes escondia — um X1 de −0,1 cm era impresso como 0,1 (visto no 6EX),
    invertendo o lado para quem monta o campo.
    """
    res: dict[str, float | None] = {}
    for dev in getattr(cp0, "BeamLimitingDevicePositionSequence", []):
        tipo = str(getattr(dev, "RTBeamLimitingDeviceType", "")).upper()
        try:
            pos = list(getattr(dev, "LeafJawPositions", []) or [])
        except TypeError:
            continue   # VM=1 (malformado): pydicom devolve escalar, não par
        if len(pos) < 2:
            continue
        if tipo in {"X", "ASYMX"}:
            res["x1"], res["x2"] = _troca_sinal(_cm(pos[0])), _cm(pos[1])
        elif tipo in {"Y", "ASYMY"}:
            res["y1"], res["y2"] = _troca_sinal(_cm(pos[0])), _cm(pos[1])
    return res


def _filtro_do_feixe(beam: Dataset, cp0: Dataset) -> str:
    """Filtro (cunha) do feixe, como o console mostra: ``"W60"``, ou ``"-"``.

    O Monaco usa cunha motorizada nos campos 3D (``WedgeID`` = W15/W30/W45/W60) e
    é um parâmetro de tratamento — quem monta o campo precisa ver na ficha. Sem
    ``WedgeID`` cai no ângulo (``"60°"``). Cunha declarada mas RETIRADA sai como
    ``"-"``: ela não entra no campo.

    "Retirada" é OUT em TODOS os pontos de controle, não só no primeiro. Cunha
    motorizada é exatamente o caso em que o campo tem um segmento aberto e outro
    com a cunha: olhando só o CP0, um campo entregue COM cunha (OUT no primeiro
    segmento, IN depois) saía com "-" na linha Filtro.
    """
    cunhas = list(getattr(beam, "WedgeSequence", []) or [])
    if not cunhas:
        return "-"
    cps = list(getattr(beam, "ControlPointSequence", []) or []) or [cp0]
    dentro, mencionadas = set(), set()
    for cp in cps:
        for w in (getattr(cp, "WedgePositionSequence", []) or []):
            num = getattr(w, "ReferencedWedgeNumber", None)
            if num is None:
                continue
            mencionadas.add(int(num))
            if str(getattr(w, "WedgePosition", "") or "").upper() != "OUT":
                dentro.add(int(num))
    fora = mencionadas - dentro
    rotulos = []
    for w in cunhas:
        num = getattr(w, "WedgeNumber", None)
        if num is not None and int(num) in fora:
            continue
        nome = str(getattr(w, "WedgeID", "") or "").strip()
        if not nome:
            ang = getattr(w, "WedgeAngle", None)
            nome = f"{int(float(ang))}°" if ang not in (None, "") else "Sim"
        rotulos.append(nome)
    return "/".join(rotulos) if rotulos else "-"


def _energia_rotulo(beam: Dataset, cp0: Dataset) -> str:
    """Energia no formato da ficha: '10FFF', '6 MV', '9 MeV'."""
    energia = getattr(cp0, "NominalBeamEnergy", None)
    if energia is None:
        return ""
    radiacao = str(getattr(beam, "RadiationType", "")).upper()
    unidade = "MeV" if radiacao == "ELECTRON" else "MV"
    # Modo de fluência FFF (flattening filter free).
    fff = False
    for fm in getattr(beam, "PrimaryFluenceModeSequence", []):
        if str(getattr(fm, "FluenceModeID", "")).upper() == "FFF":
            fff = True
        if str(getattr(fm, "FluenceMode", "")).upper() == "NON_STANDARD" and getattr(
            fm, "FluenceModeID", ""
        ):
            fff = str(fm.FluenceModeID).upper() == "FFF"
    return f"{energia:g}FFF" if fff else f"{energia:g} {unidade}"



def _coletar_ssds(beams) -> dict:
    """Retorna {angulo_norm: (ssd_cm, tipo)} lendo SourceToSurfaceDistance de todos os feixes."""
    ssds: dict[int, tuple] = {}
    for beam in beams:
        cps = getattr(beam, "ControlPointSequence", [])
        if not cps:
            continue
        cp0 = cps[0]
        ssd_raw = getattr(cp0, "SourceToSurfaceDistance", None)
        ang = getattr(cp0, "GantryAngle", None)
        if ssd_raw is None or ang is None:
            continue
        tipo = str(getattr(beam, "TreatmentDeliveryType", "TREATMENT")).upper()
        ang_norm = round(float(ang)) % 360
        ssd_cm = _cm(ssd_raw)
        if ang_norm not in ssds or tipo == "SETUP":
            ssds[ang_norm] = (ssd_cm, tipo)
    return ssds


def _buscar_ssd(ssds: dict, alvo: int, tipo_pref: str = "SETUP", tol: int = 10) -> float | None:
    """Busca SSD mais próximo do ângulo alvo, preferindo o tipo indicado."""
    melhor_v, melhor_diff = None, tol + 1
    melhor_v2, melhor_diff2 = None, tol + 1
    for ang, (v, t) in ssds.items():
        diff = min(abs(ang - alvo), 360 - abs(ang - alvo))
        if diff <= tol:
            if t == tipo_pref and diff < melhor_diff:
                melhor_v, melhor_diff = v, diff
            if diff < melhor_diff2:
                melhor_v2, melhor_diff2 = v, diff
    return melhor_v if melhor_v is not None else melhor_v2


def _gating_do_plano(ds: Dataset) -> tuple[bool, str]:
    """Lê o gating do RT Plan: ``(tem_gating, tecnica)``.

    A técnica de compensação de movimento respiratório fica em
    ``PatientSetupSequence[*]`` → ``MotionSynchronizationSequence`` (300A,0410)
    → ``RespiratoryMotionCompensationTechnique`` (0018,9170). Termos definidos:
    ``NONE`` / ``GATING`` / ``TRACKING`` / ``BREATH_HOLD`` / ``REALTIME``.
    O plano NÃO distingue amplitude de fase — ambos caem em ``GATING``.
    """
    for ps in getattr(ds, "PatientSetupSequence", []):
        for msq in getattr(ps, "MotionSynchronizationSequence", []):
            tec = str(getattr(msq, "RespiratoryMotionCompensationTechnique", "")
                      or "").upper()
            if tec and tec != "NONE":
                return True, tec
    return False, ""


def janela_fase_de_texto(texto: str) -> tuple[int, int] | None:
    """Janela de fase (%) a partir da descrição de uma série 4DCT.

    Reconstruções por fase nomeiam as fases usadas na descrição da série, ex.:
    ``"Ave(7) 20%_30%_40%_50%_60%_70%_80%"`` → ``(20, 80)``. Exige ao menos
    duas fases distintas (uma janela, não um instante único); ``None`` caso
    contrário.
    """
    import re
    fases = sorted({int(m) for m in re.findall(r"(\d{1,3})\s*%", texto or "")
                    if 0 <= int(m) <= 100})
    return (fases[0], fases[-1]) if len(fases) >= 2 else None


def descricao_indica_breath_hold(texto: str) -> bool:
    """True se a descrição da série de TC indica respiração suspensa (DIBH).

    Alguns TPS exportam o DIBH como técnica ``GATING`` (gate no marcador externo
    em apneia inspiratória), sem ``MOTIONMTPROTOCOL``. Aí a modalidade só aparece
    na descrição da série: ``INSP FORCADA``, ``DIBH``, ``Breath Hold``, ``Apneia``.
    Termos de 4DCT (fases em %) NÃO caem aqui — esses são amplitude/fase.
    """
    import re
    t = str(texto or "").lower()
    # "inspir" sozinho não basta: casaria com fases 4DCT em inglês
    # ("Inspiration"/"Inspiratory"). Só conta como breath-hold quando vem com
    # contexto de apneia/forçada ("inspiração forçada", "breath-hold inspiration").
    inspir_apneia = "inspir" in t and ("forc" in t or "forç" in t
                                       or "hold" in t or "apne" in t)
    return bool(
        "dibh" in t or "apne" in t or "breathhold" in t
        or re.search(r"\binsp\b", t)          # "INSP FORCADA" (abreviação do serviço)
        or ("breath" in t and "hold" in t)
        or inspir_apneia
    )


def _texto_mp(mp_ds: Dataset) -> str:
    """Junta, em minúsculas, todo o texto legível do MOTIONMTPROTOCOL.

    O protocolo da Varian guarda a definição do gate em tags privadas
    (0x3283,…) como sequências aninhadas cruas (bytes). Basta varrer os valores
    de bytes/str dos elementos e concatenar — a distinção amplitude×fase está no
    vocabulário desse texto (ver ``modalidade_gating_do_mp``).
    """
    partes: list[str] = []
    for el in mp_ds:
        v = getattr(el, "value", None)
        if isinstance(v, (bytes, bytearray)):
            partes.append(bytes(v).decode("latin1", "ignore"))
        elif isinstance(v, str):
            partes.append(v)
    return " ".join(partes).lower()


def modalidade_gating_do_mp(mp_ds: Dataset) -> str:
    """Modalidade de gating (``Amplitude``/``Fase``) lida do MOTIONMTPROTOCOL.

    É a única fonte que distingue as duas: o RT Plan e a descrição da série
    4DCT não distinguem (todo 4DCT é reconstruído em fases, mesmo quando o gate
    é por amplitude). No protocolo, o gate por posição/amplitude traz um limiar
    em ``millimeter`` (``CALCMAX``); o gate por fase traz a propriedade
    ``Phase`` em graus (``degree``). Retorna ``""`` quando ambíguo — aí o
    usuário escolhe.
    """
    txt = _texto_mp(mp_ds)
    tem_amplitude = "millimeter" in txt or "calcmax" in txt
    tem_fase = "phase" in txt and ("degree" in txt or "deg" in txt)
    if tem_amplitude and not tem_fase:
        return constantes.MOD_AMPLITUDE
    if tem_fase and not tem_amplitude:
        return constantes.MOD_FASE
    return ""


def mp_ref_plano_uid(mp_ds: Dataset) -> str:
    """SOPInstanceUID do RT Plan referenciado por um MOTIONMTPROTOCOL."""
    return _primeira_ref(mp_ds, "ReferencedInstanceSequence")


def enriquecer_gating(rp: dict, ct_descricao: str = "",
                      mp_ds: Dataset | None = None) -> None:
    """Completa modalidade e janela de gating no ``rp`` já parseado, in place.

    O RT Plan só diz *se* há gating (ver ``_gating_do_plano``) — não distingue
    amplitude de fase nem informa a janela. Aqui deduz-se o que os dados
    permitem, sem sobrescrever o que já houver no ``rp``:

    * ``BREATH_HOLD`` → Breath-Hold, direto do plano;
    * caso contrário, a modalidade vem do ``mp_ds`` (MOTIONMTPROTOCOL);
    * sendo Fase, a janela (%) vem da descrição da série 4DCT (``ct_descricao``).

    **A descrição da série vence o "amplitude" do MP** (04/09/2026): o
    protocolo não distingue DIBH de gating por amplitude em respiração livre,
    porque no RPM da Varian o DIBH É uma janela de amplitude. Quem separa os
    dois é como a imagem foi adquirida — ver o comentário no corpo. A FASE
    continua vindo antes, porque ela é distinguível no MP.

    Sem ``mp_ds``, a modalidade fica em branco para o usuário escolher — EXCETO
    quando a descrição da série indica respiração suspensa (``INSP FORCADA``,
    ``DIBH``…): muitos TPS exportam o DIBH como técnica GATING (gate no marcador
    externo em apneia), sem MOTIONMTPROTOCOL, e aí o único sinal é a descrição.
    """
    if not rp.get("gating_plano") or rp.get("gating_modalidade"):
        return
    tec = str(rp.get("gating_tecnica", "") or "").upper()
    if tec == constantes.TEC_BREATH_HOLD:
        rp["gating_modalidade"] = constantes.MOD_BREATH_HOLD
        return
    modal = modalidade_gating_do_mp(mp_ds) if mp_ds is not None else ""
    if modal == constantes.MOD_FASE:
        rp["gating_modalidade"] = constantes.MOD_FASE
        janela = janela_fase_de_texto(ct_descricao)
        if janela is not None:
            rp["gating_fase"] = f"{janela[0]}-{janela[1]}"
    elif descricao_indica_breath_hold(ct_descricao):
        # A DESCRIÇÃO DA SÉRIE VENCE O "AMPLITUDE" DO MP — e a ordem foi
        # invertida em 04/09/2026, depois de um caso real sair com "Amplitude"
        # num paciente que estava em DIBH.
        #
        # A razão é que o MP **não distingue os dois**: no RPM da Varian, a
        # apneia inspiratória profunda É implementada como uma janela de
        # amplitude no marcador externo. Então "amplitude" no protocolo não é
        # prova contra DIBH — é exatamente o que o DIBH parece nesse nível. O
        # que separa DIBH de gating por amplitude em respiração livre é como a
        # imagem foi ADQUIRIDA, e isso só está na descrição da série
        # ("INSP FORCADA", "DIBH", "apneia"), escrita por quem adquiriu.
        #
        # A regra anterior ("o MP amplitude manda") era julgamento, não
        # medição: nem o NOTAS.md registrava um caso que a sustentasse.
        #
        # A FASE continua vindo antes, e por isso: ela É distinguível no MP —
        # 4DCT é outra aquisição, com as fases em % na própria descrição.
        rp["gating_modalidade"] = constantes.MOD_BREATH_HOLD
    elif modal == constantes.MOD_AMPLITUDE:
        rp["gating_modalidade"] = constantes.MOD_AMPLITUDE


# ── Ordem dos campos na ficha ────────────────────────────────────────────────
# A tabela sai na ordem da VOLTA DO GANTRY, não na numeração do TPS. Quem monta
# acompanha o braço girando; lida por BeamNumber, a tabela obrigava a saltar de
# 270° para 30° e voltar, e é nesse vaivém que se confere um campo duas vezes e
# outro nenhuma.
#
# A volta começa em 181° e termina em 180° — uma volta inteira no sentido
# horário a partir de logo depois do "por baixo do paciente". A âncora é fixa e
# não deduzida dos ângulos presentes: assim dois planos do mesmo paciente saem
# na mesma ordem, e a tabela de um não se lê ao contrário da do outro.
GANTRY_INICIO = 181.0

# Nomes de lado direito num rótulo de plano. Comparados como TOKEN INTEIRO: a
# letra "d" solta dentro de "esquerda" faria toda mama esquerda ser tratada como
# direita — e a ordem sairia invertida justamente no plano mais comum.
_LADO_DIREITO = frozenset({"d", "dir", "direita", "direito"})


def mama_direita(rotulo_plano: str) -> bool:
    """O rótulo do plano diz que é mama DIREITA?

    A lateralidade não vem em campo próprio no DICOM; o que existe é o
    ``RTPlanLabel`` que o serviço escreve ("MAMA D 40.05Gy@15fr"). Daí a leitura
    ser por token e não por trecho: só vale "mama" mais uma palavra inteira de
    lado direito.
    """
    tokens = _normalizar(rotulo_plano).split()
    if not any(t.startswith("mama") for t in tokens):
        return False
    return any(t in _LADO_DIREITO for t in tokens)


def _arco_do_feixe(cps) -> dict:
    """``{"gantry_fim", "gantry_sentido"}`` — vazios quando o campo é estático.

    O fim vem do ÚLTIMO control point, e não do maior ângulo visto: um arco que
    passa por 0° tem 359 no meio do caminho, e "300→359" descreveria uma volta
    que não houve.

    O sentido vem do DICOM (``GantryRotationDirection``) e não da comparação
    entre os dois ângulos, porque a comparação não decide: de 300 a 179 dá para
    ir pelos dois lados, e é o sentido que diz por onde o gantry passa —
    horário cruza o 0 (a frente do paciente), anti-horário cruza o 240.
    """
    if not cps:
        return {"gantry_fim": None, "gantry_sentido": ""}
    ini = getattr(cps[0], "GantryAngle", None)
    fim = getattr(cps[-1], "GantryAngle", None)
    sentido = str(getattr(cps[0], "GantryRotationDirection", "") or "").upper()
    if sentido in ("", "NONE") or ini is None or fim is None:
        return {"gantry_fim": None, "gantry_sentido": ""}
    # Início igual ao fim com sentido declarado é arco de volta inteira; sem o
    # sentido preenchido seria campo parado, e aí não há arco a anunciar.
    if float(ini) == float(fim) and sentido not in ("CW", "CC", "CCW"):
        return {"gantry_fim": None, "gantry_sentido": ""}
    return {"gantry_fim": fim, "gantry_sentido": sentido}


def gantry_texto(feixe: dict, casas: int = 1) -> str:
    """Como o gantry deste campo é ESCRITO: ``"90"`` ou ``"300→179 h"``.

    Um lugar só, porque o mesmo texto vai para a ficha impressa, para a tabela
    de edição e para a planilha — e três formatações do mesmo ângulo em três
    telas do mesmo programa é como se perde a confiança nas três.

    O sufixo é o SENTIDO, e ele não é enfeite: ``300→179`` sozinho é ambíguo,
    porque de 300 a 179 dá para ir pelos dois lados — horário cruza o 0° (a
    frente do paciente) e anti-horário cruza o 240°. ``h``/``ah`` em vez de
    ``CW``/``CCW`` porque a ficha é escrita em português e a coluna é estreita.
    """
    def _num(v):
        if v is None or v == "":
            return ""
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        texto = f"{f:.{casas}f}".rstrip("0").rstrip(".")
        return (texto or "0").replace(".", ",")

    ini = _num(feixe.get("gantry"))
    fim = _num(feixe.get("gantry_fim"))
    if not (ini and fim):
        return ini
    sentido = str(feixe.get("gantry_sentido") or "").upper()
    # "CC" e "CCW" são a mesma coisa em bancos diferentes; qualquer outra coisa
    # não vira letra nenhuma, porque sentido errado no papel é pior que sentido
    # nenhum — quem confere iria procurar o braço passando pelo lado errado.
    volta = {"CW": " h", "CC": " ah", "CCW": " ah"}.get(sentido, "")
    return f"{ini}→{fim}{volta}"


def _chave_gantry(feixe: dict) -> tuple:
    """Lugar do feixe na volta que começa em :data:`GANTRY_INICIO`."""
    numero = int(feixe["numero"]) if feixe.get("numero") is not None else 0
    angulo = feixe.get("gantry")
    if angulo is None:
        # Sem ângulo não há lugar na volta: vai para o fim, na ordem do TPS.
        return (1, 0.0, numero)
    return (0, (float(angulo) - GANTRY_INICIO) % 360.0, numero)


# Dose por fração (cGy) a partir da qual a ficha SEGUE A ORDEM DO TPS em vez
# da volta do gantry. Acima de 600 cGy/fração o tratamento é hipofracionado — o
# planejamento escolhe a sequência dos campos, e ela é parte do plano: mudá-la
# para ler melhor a volta do braço faria a ficha discordar do que está no
# console, na única classe de caso em que a sequência importa. Decisão do
# usuário, 31/08/2026.
DOSE_ORDEM_DO_TPS_CGY = 600.0


def ordem_e_do_tps(dose_fracao_gy) -> bool:
    """A dose por fração (em Gy) manda seguir a ordem do TPS?

    Sem dose não se decide nada: ``None`` é "não sei", e vale a volta do
    gantry, que é como a ficha sempre saiu.
    """
    try:
        return float(dose_fracao_gy) * 100.0 > DOSE_ORDEM_DO_TPS_CGY
    except (TypeError, ValueError):
        return False


def ordem_do_tps(feixes: list) -> list:
    """Os feixes na ordem em que o TPS os exportou.

    Ordena por ``ordem_tps`` — a POSIÇÃO na ``BeamSequence`` do RT Plan, que é
    o que o planejamento define. Feixe sem essa marca (registro JSON antigo,
    feixe montado à mão) desempata pelo número, e vai para o fim.
    """
    def _chave(f):
        pos = f.get("ordem_tps")
        numero = int(f["numero"]) if f.get("numero") is not None else 0
        return (1, numero) if pos is None else (0, int(pos))
    return sorted(feixes, key=_chave)


def ordenar_feixes(feixes: list, rotulo_plano: str = "",
                   dose_fracao=None) -> list:
    """Os feixes na ordem em que o gantry passa por eles.

    Horário para todo plano, ANTI-HORÁRIO para mama direita — que é como o
    serviço monta esse caso. O anti-horário é a mesma volta ao contrário:
    começa em 180° e termina em 181°.

    Empate de ângulo (dois campos no mesmo gantry) desempata pelo número do
    feixe, para a ordem não depender de como o arquivo DICOM foi escrito.

    **Acima de 600 cGy por fração, quem manda é o TPS** (ver
    ``DOSE_ORDEM_DO_TPS_CGY``).
    """
    if ordem_e_do_tps(dose_fracao):
        return ordem_do_tps(feixes)
    ordenados = sorted(feixes, key=_chave_gantry)
    if mama_direita(rotulo_plano):
        com_angulo = [f for f in ordenados if f.get("gantry") is not None]
        sem_angulo = [f for f in ordenados if f.get("gantry") is None]
        ordenados = list(reversed(com_angulo)) + sem_angulo
    return ordenados


def parse_rtplan(ds: Dataset, *, fisicos, medicos) -> dict:
    """Prescrição, grupo de frações e tabela feixe a feixe do RT Plan.

    ``fisicos``/``medicos``: as listas canônicas (``dados.equipe``), contra as
    quais se casa o nome que o TPS gravou.
    """
    # Quem é quem muda com o TPS. No Eclipse o médico é PhysiciansOfRecord e o
    # físico é quem elaborou (OperatorsName), com o revisor como reserva. No
    # Monaco não há PhysiciansOfRecord, o RT Plan não traz OperatorsName, e quem
    # APROVA (ReviewerName) é o MÉDICO — usar o revisor como físico, que é a
    # regra do Eclipse, punha o médico no campo do físico. O físico do Monaco vem
    # do RT Struct (ver ``completar_equipe``).
    _elekta = "elekta" in str(getattr(ds, "Manufacturer", "") or "").lower()
    _revisor = getattr(ds, "ReviewerName", "")
    info: dict[str, Any] = {
        "paciente": dados_paciente(ds),
        "rotulo_plano": str(getattr(ds, "RTPlanLabel", "") or ""),
        "nome_plano": str(getattr(ds, "RTPlanName", "") or ""),
        "data_plano": _formatar_data(getattr(ds, "RTPlanDate", "")),
        "medico": _selecionar_medico(
            getattr(ds, "PhysiciansOfRecord", "") or (_revisor if _elekta else ""),
            medicos=medicos),
        "fisico": _selecionar_fisico(
            operators=getattr(ds, "OperatorsName", ""),
            reviewer="" if _elekta else _revisor,
            fisicos=fisicos, medicos=medicos,
        ),
        "aprovacao": str(getattr(ds, "ApprovalStatus", "") or ""),
    }

    # Dose de prescrição (DoseReferenceSequence).
    dose_prescrita = None
    for dref in getattr(ds, "DoseReferenceSequence", []):
        if getattr(dref, "TargetPrescriptionDose", None) is not None:
            dose_prescrita = float(dref.TargetPrescriptionDose)
            break

    # Grupo de frações: nº de frações, dose e MU (BeamMeterset) por feixe.
    # Itera todos os FractionGroups para cobrir planos com múltiplas fases
    # (boost sequencial etc.); num_fracoes vem apenas do primeiro grupo.
    num_fracoes = None
    dose_por_feixe: dict[int, float] = {}
    mu_por_feixe: dict[int, float] = {}
    beam_to_fase: dict[int, int] = {}
    grupos = getattr(ds, "FractionGroupSequence", [])
    if grupos:
        num_fracoes = getattr(grupos[0], "NumberOfFractionsPlanned", None)
        for fg in grupos:
            fase_num = int(getattr(fg, "FractionGroupNumber", 1))
            for rb in getattr(fg, "ReferencedBeamSequence", []):
                num = getattr(rb, "ReferencedBeamNumber", None)
                if num is None:
                    continue
                beam_to_fase[int(num)] = fase_num
                if getattr(rb, "BeamDose", None) is not None:
                    dose_por_feixe[int(num)] = float(rb.BeamDose)
                if getattr(rb, "BeamMeterset", None) is not None:
                    mu_por_feixe[int(num)] = float(rb.BeamMeterset)

    # Mapa de Tolerance Table: número → rótulo (ToleranceTableSequence do plano).
    _tol_map: dict[int, str] = {}
    for _tt in getattr(ds, "ToleranceTableSequence", []):
        _n = getattr(_tt, "ToleranceTableNumber", None)
        _l = constantes.abreviar_tabela_tolerancia(
            str(getattr(_tt, "ToleranceTableLabel", "") or ""))
        if _n is not None:
            _tol_map[int(_n)] = _l or str(int(_n))

    # Tabela de feixes (somente TREATMENT — SETUP é omitido).
    feixes = []
    maquina = ""
    for beam in getattr(ds, "BeamSequence", []):
        if str(getattr(beam, "TreatmentDeliveryType", "TREATMENT")).upper() == "SETUP":
            continue
        cps = getattr(beam, "ControlPointSequence", [])
        cp0 = cps[0] if cps else Dataset()
        maquina = maquina or str(getattr(beam, "TreatmentMachineName", "") or "")
        numero = getattr(beam, "BeamNumber", None)
        jaws = _mordentes(cp0)
        _iso_raw = getattr(cp0, "IsocenterPosition", None)
        _iso_coords = None
        if _iso_raw is not None:
            try:
                _iso_coords = tuple(round(float(v)) for v in _iso_raw)
            except Exception:
                pass
        feixes.append(
            {
                "numero": numero,
                "nome": str(getattr(beam, "BeamName", "") or ""),
                "fase": beam_to_fase.get(int(numero), 1) if numero is not None else 1,
                "radiacao": str(getattr(beam, "RadiationType", "") or ""),
                "tecnica": _tecnica_do_feixe(beam),
                "energia": getattr(cp0, "NominalBeamEnergy", None),
                "energia_rotulo": _energia_rotulo(beam, cp0),
                "ssd": _cm(getattr(cp0, "SourceToSurfaceDistance", None)),
                "x1": jaws.get("x1"),
                "x2": jaws.get("x2"),
                "y1": jaws.get("y1"),
                "y2": jaws.get("y2"),
                "gantry": getattr(cp0, "GantryAngle", None),
                # O FIM do arco, e o sentido. ``None`` em campo estático.
                #
                # A ficha imprimia só o ângulo do primeiro control point: num
                # VMAT de cinco arcos (caso 9000021ANA, 20/08/2026) a linha
                # Gantry saiu "300 179 300 179 300" — cinco ângulos fixos para
                # cinco arcos que varrem meia volta cada. Quem confere na sala
                # lê "gantry 300" e procura um campo parado que não existe.
                #
                # ``gantry`` continua o ângulo INICIAL e continua número: é por
                # ele que ``ordenar_feixes`` põe os campos na volta do gantry e
                # que o SSD é recalculado. Quem quiser o arco inteiro compõe os
                # dois — ver ``gantry_texto``.
                **_arco_do_feixe(cps),
                "colimador": getattr(cp0, "BeamLimitingDeviceAngle", None),
                "mesa": _mesa_angulo_console(
                    getattr(cp0, "PatientSupportAngle", None), maquina),
                "bolus": "Sim" if getattr(beam, "NumberOfBoli", 0) else "-",
                "tabela": _tol_map.get(int(_tol_n), "-") if (_tol_n := getattr(beam, "ReferencedToleranceTableNumber", None)) is not None else "-",
                "filtro": _filtro_do_feixe(beam, cp0),
                "um": mu_por_feixe.get(int(numero)) if numero is not None else None,
                "dose_feixe": dose_por_feixe.get(int(numero)) if numero is not None else None,
                "_iso_coords": _iso_coords,
                # A POSIÇÃO deste feixe na ``BeamSequence`` — a ordem em que o
                # TPS exportou o plano. Guardada porque a ficha reordena (volta
                # do gantry) e depois precisa saber desfazer: é a ordem que vale
                # acima de 600 cGy/fração e a que o botão "Ordem do TPS" da
                # Edição da Ficha repõe. ``BeamNumber`` não serve de substituto:
                # ele é identidade, e nada obriga o TPS a exportar em ordem.
                "ordem_tps": len(feixes),
            }
        )

    # Ordem da VOLTA DO GANTRY (ver ``ordenar_feixes``), e não a do BeamNumber
    # — exceto acima de 600 cGy por fração, em que vale a ordem do TPS.
    # A coluna "Campo" continua trazendo o número real de cada feixe, então
    # nada se perde ao reordenar — só se ganha a leitura contínua do braço.
    _dose_fracao = (round(dose_prescrita / num_fracoes, 2)
                    if dose_prescrita and num_fracoes else None)
    feixes = ordenar_feixes(feixes, info["rotulo_plano"], _dose_fracao)

    energias = {f["energia_rotulo"] for f in feixes if f["energia_rotulo"]}
    tecnicas = {f["tecnica"] for f in feixes if f["tecnica"]}

    # Posição do isocentro (mm) — primeiro feixe de tratamento, primeiro CP.
    # Conta isocentros únicos (arredondados ao mm mais próximo).
    iso_pos_mm = None
    _iso_set: set = set()
    for beam in getattr(ds, "BeamSequence", []):
        if str(getattr(beam, "TreatmentDeliveryType", "TREATMENT")).upper() == "SETUP":
            continue
        cps = getattr(beam, "ControlPointSequence", [])
        if not cps:
            continue
        iso_raw = getattr(cps[0], "IsocenterPosition", None)
        if iso_raw is not None:
            try:
                coords = tuple(round(float(v)) for v in iso_raw)
                _iso_set.add(coords)
                if iso_pos_mm is None:
                    iso_pos_mm = [float(v) for v in iso_raw]
            except Exception:
                pass
    n_isocentros = max(len(_iso_set), 1)
    _iso_to_idx = {coords: idx for idx, coords in enumerate(sorted(_iso_set))}
    for f in feixes:
        coords = f.pop("_iso_coords", None)
        f["iso_index"] = _iso_to_idx.get(coords, 0) if coords else 0

    # SSDs brutos do DICOM (todos os feixes, incluindo SETUP).
    _ssds_dicom = _coletar_ssds(list(getattr(ds, "BeamSequence", [])))

    # Deslocamentos de setup e posição do paciente.
    desl_lat = desl_long = desl_vert = None
    patient_position = None
    ps_seq = getattr(ds, "PatientSetupSequence", [])
    if ps_seq:
        ps = ps_seq[0]
        desl_lat  = _cm(getattr(ps, "TableTopLateralSetupDisplacement", None))
        desl_long = _cm(getattr(ps, "TableTopLongitudinalSetupDisplacement", None))
        desl_vert = _cm(getattr(ps, "TableTopVerticalSetupDisplacement", None))
        # Valor de exibição na ficha: 6EX/600CD mostram o vertical com sinal
        # invertido (convenção do console). A geometria reconverte para físico.
        if desl_vert is not None:
            desl_vert *= _mesa_vert_sign(maquina)
        patient_position = str(getattr(ps, "PatientPosition", None) or "").upper() or None
    if not patient_position:
        patient_position = str(getattr(ds, "PatientPosition", None) or "").upper() or None

    _gat_tem, _gat_tec = _gating_do_plano(ds)

    info.update(
        {
            "gating_plano": _gat_tem,
            "gating_tecnica": _gat_tec,
            "dose_total": dose_prescrita,
            "num_fracoes": num_fracoes,
            "dose_fracao": _dose_fracao,
            "maquina": maquina,
            # Fabricante do TPS que exportou o plano ("Elekta Solutions AB",
            # "Varian Medical Systems"…). A ficha usa isto para o que muda de um
            # para o outro — hoje, a linha Filtro no lugar da Tabela.
            "fabricante": str(getattr(ds, "Manufacturer", "") or ""),
            "energia": ", ".join(sorted(energias)),
            "tecnica": ", ".join(sorted(tecnicas)),
            "num_feixes": len(feixes),
            "feixes": feixes,
            "iso_pos_mm": iso_pos_mm,
            "n_isocentros": n_isocentros,
            "desl_lat":  desl_lat,
            "desl_long": desl_long,
            "desl_vert": desl_vert,
            "patient_position": patient_position,
            # SSDs: valor inicial lido do DICOM; substituído por calcular_ssds() se RS/TC disponível.
            "ssd_tp0_g0":   _buscar_ssd(_ssds_dicom, 0,   tipo_pref="SETUP"),
            "ssd_tp0_g270": _buscar_ssd(_ssds_dicom, 270, tipo_pref="SETUP"),
            "ssd_tp0_g90":  _buscar_ssd(_ssds_dicom, 90,  tipo_pref="SETUP"),
            "ssd_iso_g0":   _buscar_ssd(_ssds_dicom, 0,   tipo_pref="TREATMENT"),
            "ssd_iso_g270": _buscar_ssd(_ssds_dicom, 270, tipo_pref="TREATMENT"),
            "ssd_iso_g90":  _buscar_ssd(_ssds_dicom, 90,  tipo_pref="TREATMENT"),
        }
    )
    return info


# Tipos de estrutura considerados alvos (target).
_TIPOS_ALVO = {"PTV", "CTV", "GTV"}


def parse_rtstruct(ds: Dataset) -> dict:
    """Lista de estruturas/volumes (alvos e órgãos de risco) do RT Struct."""
    # Mapeia número da ROI -> tipo interpretado (PTV, ORGAN, EXTERNAL, ...).
    tipos: dict[int, str] = {}
    for obs in getattr(ds, "RTROIObservationsSequence", []):
        num = getattr(obs, "ReferencedROINumber", None)
        if num is not None:
            tipos[int(num)] = str(getattr(obs, "RTROIInterpretedType", "") or "")

    alvos, oars, outras = [], [], []
    for roi in getattr(ds, "StructureSetROISequence", []):
        num = getattr(roi, "ROINumber", None)
        nome = str(getattr(roi, "ROIName", "") or "")
        tipo = tipos.get(int(num), "") if num is not None else ""
        item = {"nome": nome, "tipo": tipo}
        nome_up = nome.upper()
        if tipo in _TIPOS_ALVO or any(t in nome_up for t in _TIPOS_ALVO):
            alvos.append(item)
        elif tipo in {"ORGAN", "AVOIDANCE"}:
            oars.append(item)
        elif tipo != "EXTERNAL":
            outras.append(item)

    return {
        "paciente": dados_paciente(ds),
        "rotulo": str(getattr(ds, "StructureSetLabel", "") or ""),
        "alvos": alvos,
        "orgaos_risco": oars,
        "outras": outras,
    }


def _extrair_contorno_ext(rs_ds) -> dict:
    """Retorna {z_mm: [array (N,2) de (x,y), ...]} do contorno EXTERNAL do RS.

    Delega a extração DICOM para corpo3d._contornos_body (fonte única de verdade)
    e mantém TODOS os polígonos do corte (sem a coluna Z). Ficar só com o maior
    descartaria braços/partes separadas — e o raio lateral atravessaria onde o
    braço está, devolvendo um SSD longo demais.
    """
    from isocentro.dicom.corpo3d import _contornos_body
    return {
        z: [p[:, :2] for p in polys]
        for z, polys in _contornos_body(rs_ds).items()
        if polys
    }


def _max_t_poligono(poly, ox: float, oy: float, dx: float, dy: float):
    """Maior t de interseção do raio (ox,oy)+t*(dx,dy) com UM polígono, ou None.

    Interseção raio-segmento: P(t)=O+t*D, Q(s)=A+s*(B−A).
    """
    max_t = None
    n = len(poly)
    for i in range(n):
        ax, ay = float(poly[i, 0]), float(poly[i, 1])
        bx, by = float(poly[(i + 1) % n, 0]), float(poly[(i + 1) % n, 1])
        ex, ey = bx - ax, by - ay
        det = ex * dy - ey * dx
        if abs(det) < 1e-9:
            continue
        f, g = ax - ox, ay - oy
        t = (g * ex - f * ey) / det
        s = (dx * g - dy * f) / det
        if t > 1e-9 and -1e-9 <= s <= 1.0 + 1e-9:
            if max_t is None or t > max_t:
                max_t = t
    return max_t


def _cruzamentos_externos(polys, ox: float, oy: float, dx: float, dy: float):
    """(t da pele mais externa, nº de polígonos cruzados) no sentido (dx, dy).

    A pele mais externa é a que a fonte enxerga primeiro: o raio parte de dentro
    do paciente rumo à fonte, e o feixe atinge antes de tudo a superfície mais
    distante do isocentro nessa direção — o braço ou a perna, quando estão no
    caminho. Por isso o maior t, e por isso todos os polígonos do corte contam.

    O nº de polígonos cruzados diz se uma estrutura começa/termina entre duas
    fatias — ver ``_ssd_via_rs``. Retorna (None, 0) se o raio não cruza nada.
    """
    max_t = None
    n_cruzados = 0
    for poly in polys:
        t = _max_t_poligono(poly, ox, oy, dx, dy)
        if t is None:
            continue
        n_cruzados += 1
        if max_t is None or t > max_t:
            max_t = t
    return max_t, n_cruzados


def _ray_dist_externa(polys, ox: float, oy: float, dx: float, dy: float):
    """Distância até a pele mais externa no sentido (dx, dy), ou None."""
    return _cruzamentos_externos(polys, ox, oy, dx, dy)[0]


# Espessura assumida quando o RS tem uma fatia só e não dá para medir o passo.
_ESPESSURA_PADRAO_MM = 5.0


def _tolerancia_z(zs: list) -> float:
    """Quão longe rz pode estar da fatia mais próxima antes do SSD virar chute.

    Uma espessura de corte. Dentro disso, rz está entre fatias (o pior caso é
    meia espessura) ou logo após a última, e a pele daquela fatia ainda vale.
    Além disso, rz está fora do corpo contornado: a fatia mais próxima pode
    estar a dezenas de mm, e medir a pele dela seria inventar anatomia que não
    existe naquele z. Medido nos 10 pacientes de teste, rz fica no máximo a
    1,0 mm da fatia mais próxima, com passo de 1 a 5 mm — folga de sobra.
    """
    if len(zs) < 2:
        return _ESPESSURA_PADRAO_MM
    passos = [b - a for a, b in zip(zs, zs[1:]) if b > a]
    return float(_statistics.median(passos)) if passos else _ESPESSURA_PADRAO_MM


# ── Cálculo de SSD ───────────────────────────────────────────────────────────

# Máquinas cujo console mostra o deslocamento vertical da mesa com sinal oposto
# ao valor bruto do DICOM (convenção de exibição da ficha). Só afeta o número
# impresso na coluna "Deslocamento"; a geometria do SSD usa sempre o valor
# físico (bruto do DICOM).
def _mesa_vert_sign(maquina: str) -> float:
    """+1 para máquinas padrão; -1 para 6EX/600CD (console inverte o vertical)."""
    m = constantes.identificar_maquina(maquina)
    return -1.0 if (m and m.mesa_vert_invertida) else 1.0


def _mesa_angulo_console(raw, maquina):
    """Ângulo da mesa como o console mostra na ficha.

    O DICOM traz PatientSupportAngle em IEC 61217; o console do 6EX/600CD (série
    C) mostra a escala Varian, que é ``360 − IEC`` (ex.: 315→45, 295→65, 270→90).
    As demais máquinas usam o valor do DICOM. Não afeta a geometria do SSD, que
    só olha se a mesa é 0 (coplanar) — e 0 continua 0 nas duas escalas.
    """
    if raw is None:
        return None
    m = constantes.identificar_maquina(maquina)
    if m and m.grupo_mesa == "serie_c":
        try:
            return round((360.0 - float(raw)) % 360.0, 1)
        except (TypeError, ValueError):
            return raw   # valor malformado: mantém o bruto, não derruba o plano
    return raw


def _gantry_dir_xy(theta_deg: float, pos: str) -> tuple[float, float]:
    """Vetor unitário (dx, dy) em DICOM LPS XY: DO isocentro PARA a fonte.

    Derivado da norma IEC 61217 para as quatro posições de decúbito padrão.
    O eixo Z do gantry é perpendicular ao plano axial; a rotação ocorre no
    plano XY de DICOM.

    Tabela de verificação:
        HFS  G0→(0,−1)  G90→(+1, 0)  G270→(−1, 0)
        FFS  G0→(0,−1)  G90→(−1, 0)  G270→(+1, 0)
        HFP  G0→(0,+1)  G90→(−1, 0)  G270→(+1, 0)
        FFP  G0→(0,+1)  G90→(+1, 0)  G270→(−1, 0)
    """
    t = _math.radians(float(theta_deg) % 360)
    s, c = _math.sin(t), _math.cos(t)
    if pos == "FFS":   # Feet First Supine
        return (-s, -c)
    if pos == "HFP":   # Head First Prone
        return (-s,  c)
    if pos == "FFP":   # Feet First Prone
        return ( s,  c)
    if pos != "HFS":
        _LOG.warning(
            "Posição de paciente '%s' não reconhecida em _gantry_dir_xy — "
            "usando HFS como padrão; SSDs podem estar incorretos.", pos,
        )
    return (s, -c)     # HFS (padrão) — Head First Supine


def _sinais_setup(pos: str) -> tuple[float, float, float]:
    """(lat, vert, long): sinais que levam o deslocamento da mesa (IEC 61217)
    para os eixos X, Y e Z do DICOM, conforme o decúbito. Ver ``_tp0_coords``."""
    prone = pos in ("HFP", "FFP")
    return (
        -1.0 if pos in ("FFS", "HFP") else 1.0,     # lateral  → X
        1.0 if prone else -1.0,                     # vertical → Y
        -1.0 if pos in ("FFS", "FFP") else 1.0,     # longit.  → Z
    )


def _tp0_coords(
    iso_mm: list,
    desl_lat_cm,
    desl_long_cm,
    desl_vert_cm,
    pos: str,
) -> tuple[float, float, float]:
    """Posição TP0 em mm no sistema DICOM a partir do isocentro + deslocamentos.

    Converte o vetor de deslocamento (lateral, longitudinal, vertical), dado no
    sistema da mesa IEC 61217, para coordenadas DICOM do paciente conforme a
    posição de decúbito, e soma ao isocentro. ``desl_vert_cm`` deve ser o valor
    FÍSICO (bruto do DICOM), não o de exibição do console.

    Sinais (derivados do IEC 61217 e validados empiricamente em TC1–TC6):
      lat_sign : +1 (HFS, FFP), −1 (FFS, HFP)   → eixo X DICOM
      vert_sign: −1 supino (HFS, FFS), +1 prono (HFP, FFP)   → eixo Y DICOM
      long_sign: +1 cabeça-primeiro (HFS, HFP), −1 pés-primeiro (FFS, FFP) → eixo Z DICOM
    """
    iso_x, iso_y, iso_z = float(iso_mm[0]), float(iso_mm[1]), float(iso_mm[2])
    lat_mm  = (desl_lat_cm  or 0.0) * 10.0
    long_mm = (desl_long_cm or 0.0) * 10.0
    vert_mm = (desl_vert_cm or 0.0) * 10.0

    lat_sign, vert_sign, long_sign = _sinais_setup(pos)

    return (
        iso_x + lat_sign  * lat_mm,
        iso_y + vert_sign * vert_mm,
        iso_z + long_sign * long_mm,
    )


def _ssd_via_rs(
    contornos: dict,
    src_x: float,
    src_y: float,
    rx: float,
    ry: float,
    rz: float,
    dx: float,
    dy: float,
    sad: float = _SAD_MM,
) -> float | None:
    """SSD (cm) por raycast 2D no contorno EXTERNAL do RT Struct.

    Dispara um raio de (rx, ry) em direção (dx, dy) e localiza a pele.
    A fonte fica em (src_x + sad*dx, src_y + sad*dy), onde src é o ponto
    em torno do qual a gantry rotaciona: ISO para cálculo no isocentro,
    TP0 para cálculo na posição inicial de setup.
    O SSD é a distância euclidiana da fonte à pele.
    """
    if not contornos:
        return None
    zs = sorted(contornos.keys())
    # O TPS calcula no z exato, e rz raramente cai numa fatia. Entre as duas
    # fatias que envolvem rz, o que fazer depende de o raio cruzar a MESMA
    # superfície nas duas ou não:
    #
    #   mesmo nº de polígonos cruzados → é uma superfície só, mudando de
    #     tamanho em z (corpo afinando na pelve, na cabeça): interpola, senão
    #     erraria até meia espessura de corte onde o corpo "abre".
    #
    #   nº diferente → uma estrutura começa ou termina entre as fatias (um
    #     braço, uma perna). Aí não se interpola: o feixe cruza primeiro o que
    #     estiver mais externo, e é até essa pele que o SSD é medido.
    #     Interpolar aqui misturaria o braço com o tronco e devolveria uma pele
    #     no vão de ar entre os dois — que não existe.
    dist = None
    abaixo = [z for z in zs if z <= rz]
    acima = [z for z in zs if z >= rz]
    if abaixo and acima and abaixo[-1] != acima[0]:
        z_lo, z_hi = abaixo[-1], acima[0]
        d_lo, n_lo = _cruzamentos_externos(contornos[z_lo], rx, ry, dx, dy)
        d_hi, n_hi = _cruzamentos_externos(contornos[z_hi], rx, ry, dx, dy)
        if d_lo is not None and d_hi is not None:
            if n_lo == n_hi:
                f = (rz - z_lo) / (z_hi - z_lo)
                dist = d_lo + f * (d_hi - d_lo)
            else:
                dist = max(d_lo, d_hi)
        elif d_lo is not None or d_hi is not None:
            # Só um lado cruza: o corpo termina entre as fatias. É o mesmo caso
            # de estrutura que some — vale a pele que existe, não o vazio.
            dist = d_lo if d_lo is not None else d_hi
    if dist is None:
        # rz fora do intervalo contornado (ou nenhuma das duas fatias cruza).
        # A fatia mais próxima só vale se rz estiver perto dela: além de uma
        # espessura de corte o corpo não existe naquele z, e usar a última
        # fatia contornada devolveria um SSD confiante e errado — os limites
        # de sanidade não pegam, porque o valor sai plausível.
        z_ref = min(zs, key=lambda z: abs(z - rz))
        if abs(z_ref - rz) > _tolerancia_z(zs):
            _LOG.warning(
                "SSD: z=%.1f mm está a %.1f mm da fatia contornada mais próxima "
                "(%.1f mm) — fora do corpo contornado; SSD não calculado pelo RS.",
                rz, abs(z_ref - rz), z_ref,
            )
            return None
        dist = _ray_dist_externa(contornos[z_ref], rx, ry, dx, dy)
    if dist is None:
        return None
    # fonte: (src_x + sad*dx, src_y + sad*dy)  pele: (rx + dist*dx, ry + dist*dy)
    ssd_x = (src_x - rx) + (sad - dist) * dx
    ssd_y = (src_y - ry) + (sad - dist) * dy
    ssd_mm = _math.sqrt(ssd_x * ssd_x + ssd_y * ssd_y)
    ssd_cm = ssd_mm / 10.0
    return round(ssd_cm, 1) if _SSD_MIN_CM < ssd_cm < _SSD_MAX_CM else None


def _ssd_via_ct(
    ct_serie,
    src_x: float,
    src_y: float,
    rx: float,
    ry: float,
    rz: float,
    dx: float,
    dy: float,
    sad: float = _SAD_MM,
) -> float | None:
    """SSD (cm) por raycast 3D no volume de HU da TC (limiar HU = −150 UH).

    A fonte é posicionada em (src_x + sad*dx, src_y + sad*dy): src_x/src_y é
    o ponto de referência de rotação da gantry — ISO para cálculo no isocentro,
    TP0 para cálculo na posição inicial de setup.
    Marcha de 1 mm no plano axial mais próximo de rz, amostrando a HU por
    interpolação BILINEAR; a pele é o ponto onde a HU cruza −150 UH, obtido
    por interpolação linear entre o último passo de ar e o primeiro de tecido
    (sub-milimétrico, sem o viés de meio passo).

    ct_serie: CTSerie com atributos .volume (nz, rows, cols), .ipp0, .psr, .psc, .zs
    """
    import numpy as _np  # cached in sys.modules após primeira carga

    vol  = ct_serie.volume
    ipp0 = ct_serie.ipp0
    psr  = ct_serie.psr_eff   # com sinal: neg para HFP/FFP (y inverte com linha)
    psc  = ct_serie.psc_eff   # com sinal: neg para FFS/HFP (x inverte com coluna)
    zs   = ct_serie.zs

    _, rows, cols = vol.shape

    zi = int(_np.argmin(_np.abs(zs - rz)))
    sl = vol[zi]

    # Fonte em src + SAD × dir (src = ponto de referência: TP0 ou ISO)
    src_col = (src_x + sad * dx - ipp0[0]) / psc
    src_row = (src_y + sad * dy - ipp0[1]) / psr

    def _hu(c: float, r: float):
        """HU por interpolação BILINEAR em (col=c, row=r); None se fora do FOV.

        Sem quantização por voxel mais próximo → surface mais precisa.
        """
        c0 = int(_np.floor(c)); r0 = int(_np.floor(r))
        if not (0 <= c0 < cols and 0 <= r0 < rows):
            return None
        # Vizinho clampado na borda: mantém o FOV inteiro amostrável (a última
        # linha/coluna vale o próprio voxel, sem interpolar naquele eixo).
        c1 = min(c0 + 1, cols - 1); r1 = min(r0 + 1, rows - 1)
        fc = c - c0; fr = r - r0
        v00 = float(sl[r0, c0]); v01 = float(sl[r0, c1])
        v10 = float(sl[r1, c0]); v11 = float(sl[r1, c1])
        return (v00 * (1 - fc) * (1 - fr) + v01 * fc * (1 - fr)
                + v10 * (1 - fc) * fr + v11 * fc * fr)

    STEP_MM = 1.0
    n_steps = int(sad / STEP_MM) + 20

    prev_hu = None
    prev_d = None
    for i in range(1, n_steps):
        d = i * STEP_MM
        c = src_col - d * dx / psc
        r = src_row - d * dy / psr
        hu = _hu(c, r)
        if hu is None:
            prev_hu = prev_d = None  # fora do FOV: reinicia a interpolação
            continue
        if hu > _HU_PELE:
            # Interpola o cruzamento EXATO do limiar entre o último passo de ar
            # (prev) e este de tecido — remove o viés de subestimar em ~½ passo.
            if prev_hu is not None and prev_hu <= _HU_PELE and hu != prev_hu:
                frac = (_HU_PELE - prev_hu) / (hu - prev_hu)
                d_cross = prev_d + frac * (d - prev_d)
            else:
                d_cross = d - STEP_MM * 0.5
            ssd_cm = d_cross / 10.0
            return round(ssd_cm, 1) if _SSD_MIN_CM < ssd_cm < _SSD_MAX_CM else None
        prev_hu = hu
        prev_d = d

    return None


def calcular_ssds(rp_info: dict, rs_ds=None, ct_serie=None) -> dict:
    """Calcula todos os SSDs da ficha a partir da geometria real do paciente.

    Método primário por prioridade:
      1. Contorno EXTERNAL do RT Struct — MESMA superfície que o TPS usa;
         interseção raio-polígono exata. Validado contra a ficha do TPS em
         8 pacientes / 93 ângulos: erro médio 1,9 mm (80% ≤2 mm, máx 11 mm).
      2. Volume CT por HU (ct_serie) — fallback (sem RS). Mesma validação:
         erro médio 7,3 mm (44% ≤2 mm, máx 79 mm); tem viés negativo
         sistemático no TP0 e erra muito na pelve.
      3. Nenhum disponível → retorna {}

    Calcula para os 3 ângulos padrão (G0°, G90°, G270°) no TP0 e no
    isocentro, e o SSD de cada feixe de tratamento no ângulo real do gantry.

    Returns:
        dict com ssd_tp0_g0/g90/g270, ssd_iso_g0/g90/g270 (cm),
        e "feixes" com ssd atualizado por feixe.
    """
    iso_mm = rp_info.get("iso_pos_mm")
    if not iso_mm or len(iso_mm) < 3:
        return {}

    pos = (rp_info.get("patient_position") or "HFS").upper()

    # desl_vert em rp_info é o valor de EXIBIÇÃO (console). Reconverte para o
    # valor FÍSICO (bruto do DICOM) que a geometria usa: para 6EX/600CD isso
    # desfaz a inversão de sinal aplicada em parse_rtplan (mesa_sign² = 1).
    _desl_vert_fisico = (rp_info.get("desl_vert") or 0.0) * _mesa_vert_sign(rp_info.get("maquina"))

    # Posição TP0 em mm
    tp0_x, tp0_y, tp0_z = _tp0_coords(
        iso_mm,
        rp_info.get("desl_lat"),
        rp_info.get("desl_long"),
        _desl_vert_fisico,
        pos,
    )
    iso_x, iso_y, iso_z = float(iso_mm[0]), float(iso_mm[1]), float(iso_mm[2])

    # Extrai contorno EXTERNAL do RS (método secundário)
    contornos: dict = {}
    if rs_ds is not None:
        try:
            contornos = _extrair_contorno_ext(rs_ds)
        except Exception:
            pass

    use_ct = ct_serie is not None
    use_rs = bool(contornos)

    if not use_ct and not use_rs:
        return {}

    def _calc(rx: float, ry: float, rz: float, theta_deg: float) -> float | None:
        dx, dy = _gantry_dir_xy(theta_deg, pos)
        # Prioriza o contorno EXTERNAL do RT Struct: é a MESMA superfície que o
        # TPS usa para o SSD. Medido contra a ficha do TPS em 8 pacientes / 93
        # ângulos: EXTERNAL erra em média 1,9 mm (80% ≤2 mm, máx 11) contra
        # 7,3 mm da CT (44% ≤2 mm, máx 79) — a CT ainda tem viés negativo
        # sistemático no TP0 e falha feio na pelve. A CT fica como fallback
        # (é o caminho usado quando não há RS).
        if use_rs:
            v = _ssd_via_rs(contornos, rx, ry, rx, ry, rz, dx, dy)
            if v is not None:
                return v
        if use_ct:
            return _ssd_via_ct(ct_serie, rx, ry, rx, ry, rz, dx, dy)
        return None

    out: dict[str, Any] = {
        "ssd_tp0_g0":   _calc(tp0_x, tp0_y, tp0_z,   0.0),
        "ssd_tp0_g90":  _calc(tp0_x, tp0_y, tp0_z,  90.0),
        "ssd_tp0_g270": _calc(tp0_x, tp0_y, tp0_z, 270.0),
        "ssd_iso_g0":   _calc(iso_x, iso_y, iso_z,   0.0),
        "ssd_iso_g90":  _calc(iso_x, iso_y, iso_z,  90.0),
        "ssd_iso_g270": _calc(iso_x, iso_y, iso_z, 270.0),
    }

    # SSD por feixe de tratamento no ângulo real do gantry.
    # Feixes não-coplanares (mesa != 0) são ignorados: o raycast 2D axial daria
    # resultado errado para beams que saem do plano XY.
    feixes_novos = []
    for feixe in rp_info.get("feixes", []):
        gantry = feixe.get("gantry")
        mesa = float(feixe.get("mesa") or 0.0)
        if gantry is not None and abs(mesa) < 1.0:
            feixe = dict(feixe)
            novo = _calc(iso_x, iso_y, iso_z, float(gantry))
            feixe["ssd"] = novo if novo is not None else feixe.get("ssd")
        feixes_novos.append(feixe)
    if feixes_novos:
        out["feixes"] = feixes_novos

    return out


def marcador_tp0(rs_ds) -> list | None:
    """Centro (x, y, z em mm) da ROI de marcador do TP0 no RT Struct, ou None.

    O Monaco (Elekta) contorna o ponto de referência de setup como uma ROI do
    tipo ``MARKER`` chamada ``TP0`` (às vezes com sufixo, ex.: ``TP0 SSD 100
    cm``). Nos planos em que o RT Plan também traz os deslocamentos, os dois
    concordam dentro de 0,5 mm — é o mesmo ponto.
    """
    if rs_ds is None:
        return None
    tipos = {int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", "") or "")
             for o in getattr(rs_ds, "RTROIObservationsSequence", [])}
    alvo = None
    for r in getattr(rs_ds, "StructureSetROISequence", []):
        # _normalizar devolve minúsculas, sem acento e sem pontuação; tirar os
        # espaços faz "TP 0", "TP-0" e "TP0 SSD 100 cm" caírem no mesmo prefixo.
        nome = _normalizar(str(getattr(r, "ROIName", "") or "")).replace(" ", "")
        if nome.startswith("tp0"):
            num = int(r.ROINumber)
            # Marcador tem prioridade; um volume chamado "TP0..." só serve se
            # não houver marcador nenhum.
            if tipos.get(num, "").upper() == "MARKER":
                alvo = num
                break
            if alvo is None:
                alvo = num
    if alvo is None:
        return None
    pontos: list = []
    for rc in getattr(rs_ds, "ROIContourSequence", []):
        if int(getattr(rc, "ReferencedROINumber", -1)) != alvo:
            continue
        for c in getattr(rc, "ContourSequence", []) or []:
            d = [float(v) for v in getattr(c, "ContourData", []) or []]
            pontos.extend(d[i:i + 3] for i in range(0, len(d) - 2, 3))
    if not pontos:
        return None
    n = len(pontos)
    return [sum(p[i] for p in pontos) / n for i in range(3)]


def completar_equipe(rp_info: dict, rs_ds=None, *, fisicos, medicos) -> bool:
    """Preenche o físico pelo ``OperatorsName`` do RT Struct quando o plano não traz.

    O Monaco deixa o ``OperatorsName`` do RT Plan vazio e grava no RT Struct quem
    estava logado — normalmente o login do físico (``"adriano"`` →
    ``"Adriano Henrique Dal Moro"``, pela lista canônica). Login que não casa com
    a lista é ignorado: ``"test"`` não vira nome de físico.

    Returns:
        True se preencheu (in-place); False se já havia físico ou não deu para
        reconhecer o nome.
    """
    if rp_info.get("fisico") or rs_ds is None:
        return False
    fisico = _selecionar_fisico(operators="",
                                reviewer=getattr(rs_ds, "OperatorsName", ""),
                                fisicos=fisicos, medicos=medicos)
    if not fisico:
        return False
    rp_info["fisico"] = fisico
    return True


def completar_deslocamentos(rp_info: dict, rs_ds=None) -> bool:
    """Deriva os deslocamentos de setup do marcador TP0 quando o plano não traz.

    Alguns planos do Monaco saem sem os Table Top Setup Displacements
    (300A,01D2/01D4/01D6) — vistos em SRS. Sem eles o TP0 caía em cima do
    isocentro e a ficha imprimia SSD de TP0 IGUAL ao do isocentro, sem avisar:
    o técnico alinharia no ponto errado. Com o marcador TP0 do RT Struct dá para
    recuperar o vetor exato (é a inversa de ``_tp0_coords``).

    Returns:
        True se preencheu (in-place). False se já havia deslocamento ou se não
        há marcador TP0.
    """
    if any(rp_info.get(k) is not None
           for k in ("desl_lat", "desl_long", "desl_vert")):
        return False
    iso = rp_info.get("iso_pos_mm")
    tp0 = marcador_tp0(rs_ds)
    if not iso or len(iso) < 3 or tp0 is None:
        return False
    pos = (rp_info.get("patient_position") or "HFS").upper()
    lat_s, vert_s, long_s = _sinais_setup(pos)
    # Vertical: o valor guardado em rp_info é o de EXIBIÇÃO (console), então
    # reaplica a inversão da máquina — a mesma que parse_rtplan aplica.
    vert_m = _mesa_vert_sign(rp_info.get("maquina"))
    rp_info["desl_lat"] = round((float(tp0[0]) - float(iso[0])) / 10.0 / lat_s, 2)
    rp_info["desl_vert"] = round((float(tp0[1]) - float(iso[1])) / 10.0 / vert_s * vert_m, 2)
    rp_info["desl_long"] = round((float(tp0[2]) - float(iso[2])) / 10.0 / long_s, 2)
    return True


def aplicar_ssds(rp_info: dict, rs_ds=None, ct_serie=None) -> bool:
    """Calcula e aplica SSDs em rp_info in-place. Retorna True se calculou.

    Ponto único de merge usado por gui.py e app.py.
    """
    completar_deslocamentos(rp_info, rs_ds)
    geo = calcular_ssds(rp_info, rs_ds=rs_ds, ct_serie=ct_serie)
    if not geo:
        return False
    rp_info.update({k: v for k, v in geo.items() if k != "feixes"})
    if geo.get("feixes"):
        rp_info["feixes"] = geo["feixes"]
    return True


def sinais_iop(ds) -> tuple[float, float]:
    """(sinal_linha, sinal_coluna) do ``ImageOrientationPatient`` de ``ds``.

    ``PixelSpacing`` é sempre positivo: quem diz se a coordenada CRESCE ou
    DIMINUI ao andar na grade é o IOP. Nos decúbitos usados aqui ele é axial e
    vale ±1 em cada eixo::

        HFS → [ 1,0,0,  0, 1,0]     x e y crescem
        FFS → [-1,0,0,  0, 1,0]     x inverte
        HFP → [-1,0,0,  0,-1,0]     x e y invertem (ventral)
        FFP → [ 1,0,0,  0,-1,0]     y inverte (ventral)

    ``iop[0]`` é a componente X da direção-LINHA (colunas → x) e ``iop[4]`` a
    componente Y da direção-COLUNA (linhas → y). Só o SINAL é usado: numa
    orientação oblíqua (não suportada) multiplicar pela componente encolheria o
    espaçamento, e 0 zeraria o eixo — aqui isso cai no +1, que é a leitura
    padrão. Sem IOP no dataset, assume a orientação canônica.

    Returns:
        (sinal para PixelSpacing[0]/linhas/y, sinal para PixelSpacing[1]/colunas/x)
    """
    iop = getattr(ds, "ImageOrientationPatient", None) or [1, 0, 0, 0, 1, 0]
    try:
        fx, gy = float(iop[0]), float(iop[4])
    except (TypeError, ValueError, IndexError):
        return 1.0, 1.0
    return (-1.0 if gy < 0 else 1.0), (-1.0 if fx < 0 else 1.0)


def sinal_normal_iop(ds) -> float:
    """Para que lado, em Z, apontam os offsets de corte deste dataset.

    ``GridFrameOffsetVector`` do RT Dose é medido ao longo da NORMAL do plano
    da imagem, e a normal é ``linha × coluna`` — não o eixo Z do paciente. Com
    o IOP axial dos decúbitos usados aqui, o Z da normal é ``iop[0] * iop[4]``:

        HFS  [ 1,0,0,  0, 1,0] →  +1   offsets somam
        FFS  [-1,0,0,  0, 1,0] →  -1   offsets SUBTRAEM
        HFP  [-1,0,0,  0,-1,0] →  +1
        FFP  [ 1,0,0,  0,-1,0] →  -1

    Somar sempre punha a grade do FFS a UMA GRADE INTEIRA de distância do
    paciente — medido no caso 9000021ANA (21/08/2026): estruturas em
    z −734…−5 mm e grade em z −2…+733. Sem sobreposição, o DVH sai vazio e a
    isodose some dos cortes; com sobreposição PARCIAL, que é o caso quando a
    grade é menor, sai um DVH com números plausíveis e errados — 1,15 Gy num
    tratamento de 8 Gy. Este é o defeito que a ficha não pode ter.
    """
    iop = getattr(ds, "ImageOrientationPatient", None) or [1, 0, 0, 0, 1, 0]
    try:
        fx, gy = float(iop[0]), float(iop[4])
    except (TypeError, ValueError, IndexError):
        return 1.0
    return -1.0 if (fx < 0) != (gy < 0) else 1.0


def parse_rtdose(ds: Dataset) -> dict:
    """Resumo da matriz de dose do RT Dose."""
    linhas = getattr(ds, "Rows", None)
    colunas = getattr(ds, "Columns", None)
    frames = getattr(ds, "NumberOfFrames", None)
    return {
        "paciente": dados_paciente(ds),
        "unidade": str(getattr(ds, "DoseUnits", "") or ""),
        "tipo": str(getattr(ds, "DoseType", "") or ""),
        "soma": str(getattr(ds, "DoseSummationType", "") or ""),
        "escala": getattr(ds, "DoseGridScaling", None),
        "dimensoes": f"{colunas}×{linhas}×{frames}" if linhas and colunas else "",
    }


# ---------------------------------------------------------------------------
# Múltiplos planos — associação RP ↔ RS ↔ RD por referência DICOM
# ---------------------------------------------------------------------------

MAX_PLANOS = 5


def sop_uid(ds) -> str:
    return str(getattr(ds, "SOPInstanceUID", "") or "")


def _primeira_ref(ds, atributo: str) -> str:
    """ReferencedSOPInstanceUID do 1º item de uma sequência de referência."""
    for item in getattr(ds, atributo, []) or []:
        uid = str(getattr(item, "ReferencedSOPInstanceUID", "") or "")
        if uid:
            return uid
    return ""


def plano_ref_struct_uid(ds) -> str:
    """SOPInstanceUID do RT Struct referenciado por um RT Plan."""
    return _primeira_ref(ds, "ReferencedStructureSetSequence")


def dose_ref_plano_uid(ds) -> str:
    """SOPInstanceUID do RT Plan referenciado por um RT Dose."""
    return _primeira_ref(ds, "ReferencedRTPlanSequence")


def _prioridade_dose(ds) -> int:
    """Ordem de preferência de um RT Dose: PLAN < FRACTION < resto < BEAM.

    O que a ficha quer é a dose do PLANO inteiro. ``BEAM`` fica por último
    (é a dose de um feixe só) e serve apenas se não houver mais nada.
    """
    soma = str(getattr(ds, "DoseSummationType", "") or "").upper()
    return {"PLAN": 0, "MULTI_PLAN": 1, "FRACTION": 2}.get(
        soma, 4 if soma == "BEAM" else 3)


def agrupar_planos(planos: list, structs: list, doses: list,
                   limite: int = MAX_PLANOS, *, fisicos, medicos) -> list[dict]:
    """Agrupa até ``limite`` RT Plans com seus RS/RD associados por referência.

    Cada item devolvido: ``{"rp_ds", "rp"(parseado), "rs_ds", "rd_ds", "rotulo"}``.
    Faz *fallback* razoável quando as referências estão ausentes (ex.: RS/RD
    único é associado ao plano único).

    ``fisicos``/``medicos``: as listas canônicas (``dados.equipe``), passadas
    ao ``parse_rtplan`` e ao ``completar_equipe``.
    """
    planos = list(planos)[:limite]
    structs = list(structs)
    doses = list(doses)

    structs_por_uid = {sop_uid(s): s for s in structs}
    bundles: list[dict] = []
    for i, p in enumerate(planos, start=1):
        rs = structs_por_uid.get(plano_ref_struct_uid(p))
        if rs is None and len(structs) == 1:
            rs = structs[0]
        rp = parse_rtplan(p, fisicos=fisicos, medicos=medicos)
        completar_equipe(rp, rs, fisicos=fisicos, medicos=medicos)
        rotulo = rp.get("rotulo_plano") or rp.get("nome_plano") or f"Plano {i}"
        bundles.append({"rp_ds": p, "rp": rp, "rs_ds": rs,
                        "rd_ds": None, "rotulo": rotulo})

    # Associa cada dose ao seu plano por ReferencedRTPlanSequence. A dose do
    # PLANO tem prioridade sobre a de um feixe: o Monaco (Elekta) exporta, além
    # da soma, um RT Dose POR FEIXE (``..._Dose_RxA_Bm1.dcm``), todos apontando
    # para o mesmo plano — pegar o primeiro que aparecesse mostraria a dose de um
    # feixe só no colorwash e no DVH.
    doses = sorted(doses, key=_prioridade_dose)
    plano_por_uid = {sop_uid(b["rp_ds"]): b for b in bundles}
    for d in doses:
        b = plano_por_uid.get(dose_ref_plano_uid(d))
        if b is not None and b["rd_ds"] is None:
            b["rd_ds"] = d
    # Fallback: dose única para plano único.
    if len(bundles) == 1 and bundles[0]["rd_ds"] is None and doses:
        bundles[0]["rd_ds"] = doses[0]

    return bundles
