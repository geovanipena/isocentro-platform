"""Extrai dos PPRs vigentes a semente do PPR vivo: cada parte com o seu dono.

Uso: ``python tools/semente_ppr.py CEL`` (BET e DUO vêm do PDF; ainda não).

Lê ``Documents\\isocentro\\servico\\<CLINICA>\\ppr\\fonte\\`` e grava
``...\\ppr\\semente.json`` — **fora do git**, porque o PPR traz nome e CPF da
equipe e a lista de ASOs (decisão de 28/10/2026). O resumo no terminal é só
contagem: o conteúdo pessoal nunca passa pela tela nem pelo log.

A semente é a PRIMEIRA versão de cada parte (spec Documentação CAP-11 e as
CAP de seções dos outros módulos): cada uma cita de onde veio, para que o
importador grave no banco com a origem, e o PPR vivo comece igual ao vigente.

Formato::

    {"clinica", "documento": {...}, "condicoes": [...],
     "partes": {"<chave>" | "anexo/<chave>": {"modulo", "texto",
                "documentos": [{"titulo", "arquivo"}], "fonte"}},
     "dados": {"<modulo>": {...}}}

As tabelas não são guardadas como tabela: são os ``dados`` do módulo dono, e
o gerador as monta. Guardar as duas coisas seria guardar o mesmo número em
dois lugares, e um dia eles divergem.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isocentro.dominio import ppr  # noqa: E402

RAIZ_SERVICO = Path.home() / "Documents" / "isocentro" / "servico"

# Código do banco por pasta do serviço (a DUO é ANA no banco: torre.CLINICAS).
CODIGO = {"CEL": "CEL", "BET": "BET", "DUO": "ANA"}

_DONO = {p.chave: p.modulo for p in ppr.CAPITULOS}
_DONO.update({s.chave: s.modulo for c in ppr.CAPITULOS for s in c.subsecoes})
_DONO_ANEXO = {a.chave: a.modulo for a in ppr.ANEXOS}
_DONO_ANEXO[ppr.SEVRRA.chave] = ppr.SEVRRA.modulo


# ── CEL: o JSON do ppr-streamlit ─────────────────────────────────────────────

def _corpo_cel(d: dict) -> dict:
    """O texto do corpo como o ``ppr_pdf._corpo`` o escreveu em mai/2026.

    Os gabaritos (identificação, objetivo, classificação) são reproduzidos
    aqui com o dado do JSON — é o texto que saiu no papel. Capítulo que é só
    "Vide anexo X" fica com texto vazio: o "Vide" é do gerador, que calcula a
    letra (ver ``dominio.ppr``).
    """
    inst = d.get("instalacao", {})
    tl = d.get("textos_caps", {})
    g = inst.get
    return {
        "identificacao": (
            f"O {g('nome', '')} (Número de matrícula CNEN {g('matricula_cnen', '')}) "
            f"inscrita no C.N.P.J. sob o nº {g('cnpj', '')}, encontra-se situado à "
            f"{g('rua', '')} {g('complemento', '')}– {g('bairro', '')}– "
            f"{g('cidade', '')}– {g('uf', '')}, CEP {g('cep', '')}, "
            f"Telefone para contato: {g('telefone', '')}.\n\n"
            f"O Horário de tratamento de pacientes é das {g('horario', '')}."),
        "objetivo": f"A citada instituição tem por objetivo o {g('objetivo', '')}.",
        "classificacao": (
            "De acordo com a Norma CNEN-NN-6.02, resolução 261/20, de Maio de "
            f"2020, a instalação é classificada com do GRUPO {g('grupo', '')}, "
            f"SUBGRUPO {g('subgrupo', '')}."),
        "areas": tl.get("classificacao_areas", ""),
        "acesso": tl.get("controle_acesso", ""),
        "gq": tl.get("programa_gq", ""),
        "gq_planilha": tl.get("planilha_controle", ""),
        "gq_testes": tl.get("testes_tolerancias_txt", ""),
        "gq_riscos": tl.get("analise_riscos", ""),
        "monitoracao_individual": tl.get("monitoracao_individual", ""),
        "monitoracao_areas": tl.get("monitoracao_areas", ""),
        "aso": tl.get("controle_medico", ""),
        "niveis": tl.get("niveis_operacionais", ""),
    }


# Anexo → (chaves de texto, chaves de PDF, chaves de imagem) do JSON, na ordem
# em que o ``ppr_pdf`` as põe na página.
_ANEXOS_CEL = {
    "ioes": (("intro_medicos", "responsabilidades_medicos"), (), ()),
    "responsabilidades": (("resp_titular", "resp_tecnico_texto", "resp_fisico"),
                          (), ()),
    "areas": (("classificacao_areas",),
              ("classificacao_areas", "autorizacao_funcionamento"),
              ("classificacao_areas",)),
    "equipamentos": (("anx_e_intro",), (), ()),
    "fontes": (("anx_f_intro",), (), ()),
    "instrumentos": (("intro_dosimetria", "controle_dosimetria"),
                     ("certificados_conjunto_dosimetrico", "certificados_outros"),
                     ()),
    "gq": (("intro_testes", "afericoes_trimestrais"), ("auditoria",),
           ("programa_qualidade",)),
    "gq_sevrra": ((), ("sevrra",), ()),
    "monitores": ((), ("certificados_monitores_area",), ()),
    "rejeitos": (("gerencia_rejeitos",), ("gerencia_rejeitos",),
                 ("gerencia_rejeitos",)),
    "barreiras": (("calculo_barreiras",),
                  ("calculo_blindagem", "levantamento_radiometrico"), ()),
    "monitoracao_individual": (("monitoracao_individual",),
                               ("contrato_monitoracao",), ()),
    "treinamento": (("programa_treinamento",), (), ()),
    "educacao": (("programa_educacao",), (), ()),
    "emergencia": (("procedimentos_emergencia",), ("procedimentos_emergencia",),
                   ()),
}

# Os certificados estão na pasta de anexos, mas o JSON de mai/2026 tem as
# listas vazias: o PDF daquele mês saiu sem eles. Entram pela pasta, marcados.
_PASTAS_DE_CERTIFICADO = {
    "certificados_conjunto_dosimetrico": "Certificados de Calibração/Conjunto Dosimetrico",
    "certificados_outros": "Certificados de Calibração/Outros",
    "certificados_monitores_area": "Certificados de Calibração/Monitor de Area",
}

# "Nome (2023).pdf" é a versão anterior do mesmo documento: história, não anexo.
_VERSAO_ANTIGA = re.compile(r"\(\d{4,5}\)\.\w+$")


def _relativo(caminho_no_json: str) -> str:
    """O caminho do JSON é de outra máquina; o que vale é o trecho depois de
    ``anexos/PDFs/``, que é igual na cópia em ``fonte/anexos``."""
    trecho = caminho_no_json.replace("\\", "/").split("/anexos/PDFs/", 1)[-1]
    return f"fonte/anexos/{trecho}"


def _documentos_cel(d: dict, chaves_pdf, pasta_ppr: Path) -> list:
    docs = []
    for chave in chaves_pdf:
        listados = d.get("pdfs", {}).get(chave, [])
        for caminho in listados:
            docs.append({"titulo": Path(caminho).stem,
                         "arquivo": _relativo(caminho),
                         "fonte": f"JSON pdfs.{chave}"})
        if not listados and chave in _PASTAS_DE_CERTIFICADO:
            pasta = pasta_ppr / "fonte" / "anexos" / _PASTAS_DE_CERTIFICADO[chave]
            for arq in sorted(pasta.glob("*.pdf")):
                if not _VERSAO_ANTIGA.search(arq.name):
                    docs.append({"titulo": arq.stem,
                                 "arquivo": arq.relative_to(pasta_ppr).as_posix(),
                                 "fonte": "pasta de anexos (não listado no JSON)"})
    for doc in docs:
        if not (pasta_ppr / doc["arquivo"]).exists():
            doc["falta"] = True
    return docs


def semente_cel(json_path: Path, pasta_ppr: Path) -> dict:
    d = json.loads(json_path.read_text(encoding="utf-8"))
    inst = d.get("instalacao", {})
    fonte = f"{json_path.name} (ppr-streamlit, {inst.get('mes', '')}/{inst.get('ano', '')})"
    tl = d.get("textos_caps", {})
    partes = {}
    for chave, texto in _corpo_cel(d).items():
        partes[chave] = {"modulo": _DONO[chave], "texto": texto,
                         "documentos": [], "fonte": fonte}
    for cap in ppr.CAPITULOS:
        partes.setdefault(cap.chave, {"modulo": cap.modulo, "texto": "",
                                      "documentos": [], "fonte": fonte})
        for sub in cap.subsecoes:
            partes.setdefault(sub.chave, {"modulo": sub.modulo, "texto": "",
                                          "documentos": [], "fonte": fonte})
    for chave in list(_DONO_ANEXO):
        textos, pdfs, imagens = _ANEXOS_CEL.get(chave, ((), (), ()))
        texto = "\n\n".join(tl.get(k, "") for k in textos if tl.get(k))
        docs = _documentos_cel(d, pdfs, pasta_ppr)
        for k in imagens:
            for img in d.get("imagens", {}).get(k, []):
                docs.append({"titulo": Path(img).stem, "arquivo": _relativo(img),
                             "fonte": f"JSON imagens.{k}"})
        partes[f"anexo/{chave}"] = {"modulo": _DONO_ANEXO[chave], "texto": texto,
                                   "documentos": docs, "fonte": fonte}
    equipe = {k[len("equipes_"):]: v for k, v in d.items()
              if k.startswith("equipes_")}
    dados = {
        "fundacao": {
            "instalacao": inst,
            "titulares": d.get("responsaveis", []),
            "funcoes": {k: d.get(k, {}) for k in (
                "supervisor", "substituto_supervisor", "responsavel_tecnico",
                "substituto_rt", "diretor_clinico")},
            "equipe": equipe,
        },
        "qualidade": {k: d.get(k, []) for k in (
            "equipamentos", "fontes_referencia", "conjunto_dosimetrico",
            "instrumentos_medicao", "outros_detectores", "fantomas",
            "monitores_area", "testes_diarios", "testes_mensais",
            "testes_anuais", "testes_diarios_braqui",
            "testes_trimestrais_braqui", "testes_mensais_orto")},
        "plano": {k: d.get(k, []) for k in (
            "sistemas_planejamento", "tecnicas_tratamento")},
        "documentacao": {"asos": d.get("asos", []),
                         "vencimentos": d.get("vencimentos", {})},
    }
    # Fonte radioativa: a CEL tem HDR (GammaMed). A resposta definitiva é do
    # inventário da GQ (R-84); aqui vale o que o PPR vigente já trazia.
    condicoes = [ppr.FONTE_RADIOATIVA] if (
        d.get("testes_diarios_braqui") or tl.get("gerencia_rejeitos")) else []
    planta = ppr.planta(frozenset(condicoes))
    for p in partes.values():
        p["texto"] = _sem_vide(p["texto"], planta)
    return {"clinica": CODIGO["CEL"],
            "documento": {"arquivo": f"fonte/{json_path.name}",
                          "data": f"{inst.get('mes', '')}/{inst.get('ano', '')}"},
            "condicoes": condicoes, "partes": partes, "dados": dados}


def copiar_anexos_cel(origem: Path, pasta_ppr: Path) -> None:
    """Copia ``anexos/PDFs`` do projeto do PPR, sem a pasta de ASOs: o ASO
    não entra no PPR vivo (Documentação CAP-3: só pessoa, data e validade)."""
    destino = pasta_ppr / "fonte" / "anexos"
    for arq in origem.rglob("*"):
        if arq.is_file() and "ASOS" not in arq.relative_to(origem).parts:
            alvo = destino / arq.relative_to(origem)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            if not alvo.exists():
                shutil.copy2(arq, alvo)


# ── BET e DUO: o PDF ────────────────────────────────────────────────────────
#
# Os dois PDFs saíram do projeto LaTeX do PPR, em versões diferentes: a DUO
# numera as seções dos anexos 1, 2, 3… e a BET 7.11, 7.12… Todo título
# (capítulo, anexo e seção) está em 17,2 pt nas duas, e é por aí que se
# recorta. O resto é escolha pela forma do conteúdo, não pela legenda: na BET
# a "Tabela G.4 – Fantoma" é de detectores, e as tabelas escorregam para depois
# da seção seguinte.

_TAMANHO_DE_TITULO = 16.0

# Seção de anexo que é documento de origem embutido, não texto do PPR.
_SECAO_DOCUMENTO = re.compile(
    r"certificad|sevrra|projeto de blindagem|levantamento|contrato|normas para"
    r"|proximidades|planilha de controle de qualidade", re.I)


@dataclass
class _Item:
    pagina: int
    y: float
    tipo: str               # "titulo" | "linha" | "tabela" | "embutida"
    texto: str = ""
    linhas: list = field(default_factory=list)   # da tabela


def _normal(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).upper().strip()


def _fontes_do_corpo(doc) -> set:
    """As fontes do texto do PPR: as que mais aparecem nas páginas 9–16.
    Página de anexo sem nenhuma delas é documento embutido (certificado,
    contrato, SEVRRA)."""
    conta: dict = {}
    for page in doc.pages(8, min(16, doc.page_count)):
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["text"].strip() and s["size"] < _TAMANHO_DE_TITULO:
                        conta[s["font"]] = conta.get(s["font"], 0) + len(s["text"])
    total = sum(conta.values())
    return {f for f, n in conta.items() if n > 0.05 * total}


def _itens(doc) -> list:
    """O documento como uma fila de títulos, linhas e tabelas, na ordem."""
    import pymupdf
    fontes = _fontes_do_corpo(doc)
    itens = []
    for pno, page in enumerate(doc, start=1):
        altura = page.rect.height
        tabelas = page.find_tables().tables
        caixas = [pymupdf.Rect(t.bbox) for t in tabelas]
        do_ppr = False
        da_pagina = []
        fontes_na_tabela = [[] for _ in caixas]
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"].strip()]
                if not spans:
                    continue
                caixa = pymupdf.Rect(l["bbox"])
                dentro = next((i for i, c in enumerate(caixas)
                               if c.contains(caixa.tl + (1, 1))), None)
                if dentro is not None:
                    fontes_na_tabela[dentro].extend(s["font"] for s in spans)
                    continue
                texto = _limpo(page.get_text("text", clip=caixa))
                if not texto or texto.startswith("Docusign Envelope"):
                    continue
                if caixa.y0 > altura * 0.88 and texto.isdigit():
                    continue            # número da página
                titulo = spans[0]["size"] >= _TAMANHO_DE_TITULO
                do_ppr = do_ppr or (not titulo and spans[0]["font"] in fontes)
                # A fonte decide se a PÁGINA é do PPR, não a linha: o nome
                # da máquina vem em negrito, que é minoria e ficaria de fora.
                da_pagina.append(_Item(pno, caixa.y0, "titulo" if titulo else "linha", texto))
        # Tabela de certificado embutido (BET, anexo G) tem cabeçalho e
        # linhas, e sem este filtro virava instrumento com "GAMA 60Co" no
        # lugar do item.
        tabelas = [t for t, f in zip(tabelas, fontes_na_tabela)
                   if f and sum(x in fontes for x in f) > len(f) / 2]
        for t in tabelas:
            da_pagina.append(_Item(pno, t.bbox[1], "tabela", linhas=t.extract()))
        if not do_ppr and not tabelas:
            # Página sem texto do PPR: documento embutido (ou só o título da
            # seção dele). O título fica; o resto vira marca de página.
            da_pagina = [i for i in da_pagina if i.tipo == "titulo"]
            da_pagina.append(_Item(pno, altura, "embutida"))
        itens.extend(sorted(da_pagina, key=lambda i: i.y))
    return _juntar_titulos(itens)


_INICIO_DE_TITULO = re.compile(r"^(ANEXO\s*[A-Z]\b|\d+(\.\d+)*\b)")


def _juntar_titulos(itens: list) -> list:
    """"12 DESCRIÇÃO DO PROGRAMA DE GARANTIA DA QUALI-" + "DADE" é um título;
    "1" + "Planilha de Controle" é outro. Começa título novo a linha que abre
    com número ou com "ANEXO"; as outras continuam o anterior."""
    saida = []
    for it in itens:
        anterior = saida[-1] if saida else None
        continua = (it.tipo == "titulo" and anterior is not None
                    and anterior.tipo == "titulo" and anterior.pagina == it.pagina
                    and not _INICIO_DE_TITULO.match(it.texto))
        numero_so = (anterior is not None and anterior.tipo == "titulo"
                     and re.fullmatch(r"\d+(\.\d+)*", anterior.texto)
                     and it.tipo == "titulo" and anterior.pagina == it.pagina)
        if continua or numero_so:
            junta = "" if anterior.texto.endswith("-") and not numero_so else " "
            anterior.texto = (anterior.texto.rstrip("-") if junta == "" else anterior.texto) + junta + it.texto
        else:
            saida.append(it)
    return saida


def _parecido(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normal(a), _normal(b)).ratio()


_VIDE = re.compile(r"\bVide\s+(?:a\w+\s+)?[A-Z]\b(?:\s+e\s+se[cç][aã]o\s+[\d.]+?)?\.?(?=\s|$)")
_MENCAO_A_ANEXO = re.compile(r"\banexo\s+([A-R])\b")


# O PDF da BET traz o "º" como "ž" (codificação da fonte) e ligaduras.
_GLIFOS = {"nž": "nº", "Nž": "Nº", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff",
           "ﬃ": "ffi", "ﬄ": "ffl"}


def _limpo(texto: str) -> str:
    for de, para in _GLIFOS.items():
        texto = texto.replace(de, para)
    return re.sub(r"\s+", " ", texto).strip()


def _celula(valor) -> str:
    """Quebra dentro da célula: "Electro-↵meter" é uma palavra, mas
    "1014300MW-↵94167003" é um número de série com hífen."""
    valor = valor or ""
    valor = re.sub(r"(?<=[a-zà-ú])-\s*\n\s*(?=[a-zà-ú])", "", valor)
    valor = re.sub(r"-\s*\n\s*", "-", valor)
    return _limpo(valor)


def _texto(linhas: list) -> str:
    """Linhas do PDF de volta a parágrafos: hifenização desfeita, e a quebra
    de parágrafo onde a linha anterior fecha frase."""
    out = ""
    for l in linhas:
        if not out:
            out = l
        elif re.search(r"[A-Za-zÀ-ú]-$", out) and re.match(r"[a-zà-ú]", l):
            # Só hifenização de palavra: "0001-" + "37" é o CNPJ, e perdia
            # o hífen.
            out = out[:-1] + l
        elif re.search(r"\d-$", out) and re.match(r"\d", l):
            out += l
        elif re.search(r"[.:;]$", out):
            out += "\n\n" + l
        else:
            out += " " + l
    return out.strip()


def _sem_vide(texto: str, planta=None) -> str:
    """O "Vide anexo X" é do gerador, que calcula a letra; a menção a anexo
    no meio do texto ("diagrama apresentado no anexo D") vira
    ``{anexo:areas}`` pelo mesmo motivo — com letra fixa, o PPR de uma
    clínica que ganhe ou perca fonte radioativa apontaria para o anexo
    errado."""
    texto = _VIDE.sub("", texto).strip()
    if planta is not None:
        por_letra = {l: a.chave for l, a in planta.anexos}
        texto = _MENCAO_A_ANEXO.sub(
            lambda m: f"anexo {{anexo:{por_letra[m.group(1)]}}}"
            if m.group(1) in por_letra else m.group(0), texto)
    return texto


def _paginas(nums: list) -> str:
    nums = sorted(set(nums))
    if not nums:
        return ""
    faixas, ini, ant = [], nums[0], nums[0]
    for n in nums[1:]:
        if n != ant + 1:
            faixas.append(f"{ini}-{ant}" if ant > ini else f"{ini}")
            ini = n
        ant = n
    faixas.append(f"{ini}-{ant}" if ant > ini else f"{ini}")
    return ",".join(faixas)


# ── Tabelas → dados ──────────────────────────────────────────────────────────

_CABECALHO = {           # palavra do cabeçalho normalizado → campo
    "FONTE SELADA": "obj", "ITEM": "obj", "TESTE": "teste", "TOLERANCIA": "tolerancia",
    "TIPO": "tipo", "FABRICANTE": "fabricante", "MODELO": "modelo", "SERIE": "serie",
    "DATA": "data", "FABRICACAO": "data", "ATIVIDADE": "atividade",
    "DIMENSOES": "dimensoes", "MATERIAL": "material", "NOME": "nome", "IOE": "nome",
    "CRM": "crm", "RB": "rb", "RT": "rt", "RA": "ra", "FORMACAO": "formacao",
    "CRTR": "crtr", "COREN": "coren", "CARGA": "carga", "CARGO": "cargo",
    "EQUIPE": "cargo", "FUNCAO": "cargo", "REGISTRO": "registro", "ULTIMO": "ultimo",
    "VALIDADE": "validade",
}


def _campo(cabecalho: str) -> str:
    """Por palavra inteira: por pedaço, "RA" casava com "CARGA HORÁRIA" e
    "RT" com "CRTR", e a carga horária dos médicos virava registro."""
    n = _normal(cabecalho or "")
    palavras = re.findall(r"[A-Z]+", n)
    for chave, campo in _CABECALHO.items():
        if (chave in n) if " " in chave else (chave in palavras):
            return campo
    return ""


def _colar(a: str, b: str) -> str:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return a or b
    return a + ("" if a.endswith(("/", "-")) or b.startswith("/") else " ") + b


def _registros(linhas: list) -> list:
    """Tabela do PDF → lista de dicionários pelo cabeçalho.

    Coluna sem nome reconhecível é pedaço da anterior ("Data brica" | "Fa-
    ção" na fonte da DUO): o valor cola no da esquerda. Linha só com a
    primeira célula, ou só com as outras, continua a de cima ("(modos de
    irradiação; aplicadores…)" do teste de travas).
    """
    if not linhas:
        return []
    cab = [_celula(c) for c in linhas[0]]
    campos = [_campo(c) for c in cab]
    primeiro = campos[0]
    regs, prefixo = [], ""
    for linha in linhas[1:]:
        reg: dict = {}
        ultimo = ""
        for campo, valor in zip(campos, linha):
            valor = _celula(valor)
            alvo = campo or ultimo
            if alvo:
                reg[alvo] = _colar(reg.get(alvo, ""), valor)
            ultimo = alvo
        cheios = {k for k, v in reg.items() if v}
        if not cheios:
            continue
        if cheios == {primeiro}:
            # Só a 1ª célula: "(modos de irradiação…)" e "especificações do
            # fabricante)" fecham a linha de CIMA; "Detector" (BET, G.4)
            # abre a de BAIXO.
            if regs and re.match(r"^[a-zà-ú(]", reg[primeiro]):
                regs[-1][primeiro] = _colar(regs[-1].get(primeiro, ""), reg[primeiro])
            else:
                prefixo = _colar(prefixo, reg[primeiro])
            continue
        if regs and primeiro not in cheios:
            for k in cheios:
                regs[-1][k] = _colar(regs[-1].get(k, ""), reg[k])
            continue
        if prefixo:
            reg[primeiro] = _colar(prefixo, reg.get(primeiro, ""))
            prefixo = ""
        regs.append(reg)
    return regs


def _tipo_de_tabela(registros: list, cab: str, anexo: str) -> str:
    n = _normal(cab)
    if "TESTE" in n:
        return "testes"
    if "FONTE SELADA" in n:
        return "fontes_referencia"
    if "DIMENSOES" in n or "MATERIAL" in n:
        return "fantomas"
    if "ULTIMO" in n or "VALIDADE" in n:
        return "asos"
    if "CRM" in n:
        return "medicos"
    if "CRTR" in n:
        return "tecnicos"
    if "COREN" in n:
        return "enfermagem"
    if "RT" in n.split() and "RA" in n.split():
        return "fisicos"
    if "NOME" in n:
        return "demais"
    if anexo == "monitores":
        return "monitores_area"
    if "TIPO" in n:
        return "outros_detectores"
    itens = _normal(" ".join(r.get("obj", "") for r in registros))
    if "CAMARA" in itens or "ELETROMETRO" in itens:
        return "conjunto_dosimetrico"
    return "instrumentos_medicao"


_FREQUENCIA = (("DIARI", "diarios"), ("MENSA", "mensais"), ("ANUA", "anuais"),
               ("TRIMESTRA", "trimestrais"), ("SEMESTRA", "semestrais"),
               ("SEMANA", "semanais"))
_TIPO_DE_TESTE = (("SEGURAN", "Segurança"), ("DOSIM", "Dosimétrico"),
                  ("MECAN", "Mecânico"))


def _testes_da_legenda(legenda: str, registros: list) -> tuple:
    n = _normal(legenda)
    freq = next((f for k, f in _FREQUENCIA if k in n), "")
    tipo = next((t for k, t in _TIPO_DE_TESTE if k in n), "")
    for r in registros:
        if tipo and not r.get("tipo"):
            r["tipo"] = tipo
    return f"testes_{freq}" if freq else "testes_sem_periodicidade", registros


# Rótulos do anexo E (equipamentos) e do J (TPS), como o ``ppr_pdf`` os escreve.
_ROTULOS = {"Fabricante": "fabricante", "Modelo": "modelo", "Nº de Série": "serie",
            "No. de Série": "serie", "Data de Fabricação": "fabricacao",
            "Data de Aceite": "aceite", "Aceite": "aceite", "Energia nominal": "energia",
            "Tipo de Radiação": "radiacao", "Taxa de dose nominal": "taxa_dose",
            "Versão": "versao", "Técnicas Implementadas": "tecnicas",
            # Grafia do PDF da BET, com o erro de digitação.
            "Ténicas Implementadas": "tecnicas", "Nome Comercial": "nome"}


def _rotulados(texto: str) -> dict:
    padrao = "|".join(re.escape(r) for r in sorted(_ROTULOS, key=len, reverse=True))
    partes = re.split(rf"({padrao}):", texto)
    reg = {}
    for i in range(1, len(partes) - 1, 2):
        reg[_ROTULOS[partes[i]]] = partes[i + 1].strip().rstrip(".")
    return reg


def semente_pdf(pdf: Path, clinica: str, pasta_ppr: Path) -> dict:
    import pymupdf
    doc = pymupdf.open(pdf)
    itens = _itens(doc)
    fonte_doc = f"{pdf.name}"
    arquivo = f"fonte/{pdf.name}"

    # Onde o corpo começa e acaba.
    ini = next(i for i, it in enumerate(itens) if it.tipo == "titulo"
               and re.match(r"^1\s*IDENTIFICA", _normal(it.texto)))
    fim = next(i for i, it in enumerate(itens) if i > ini and it.tipo == "titulo"
               and (_normal(it.texto).startswith(("REFERENCIAS", "ANEXO"))))
    tem_rejeitos = any("REJEITOS" in _normal(it.texto) for it in itens[ini:fim]
                       if it.tipo == "titulo")
    condicoes = frozenset({ppr.FONTE_RADIOATIVA}) if tem_rejeitos else frozenset()
    planta = ppr.planta(condicoes)

    partes: dict = {}
    avisos: list = []

    def parte(chave, modulo, texto="", docs=None, pags=()):
        partes[chave] = {"modulo": modulo, "texto": texto, "documentos": docs or [],
                         "fonte": f"{fonte_doc}, p. {_paginas(list(pags))}" if pags else fonte_doc}

    # ── corpo ──
    capitulos = iter(planta.capitulos)
    atual, sub, buf, pags = None, None, [], []
    numero_atual = 0

    def fechar():
        if atual is None:
            return
        chave = sub.chave if sub else atual.chave
        parte(chave, (sub or atual).modulo, _sem_vide(_texto(buf), planta), pags=pags)

    for it in itens[ini:fim]:
        if it.tipo == "titulo":
            m = re.match(r"^(\d+(?:\.\d+)*)\s*(.*)", it.texto)
            numero = m.group(1) if m else ""
            if numero.isdigit() and int(numero) == numero_atual + 1:
                fechar()
                numero_atual += 1
                _n, atual = next(capitulos)
                sub, buf, pags = None, [], [it.pagina]
                if _parecido(m.group(2), atual.titulo) < 0.6:
                    avisos.append(f"capítulo {numero}: '{m.group(2)[:50]}' ≠ '{atual.titulo}'")
                continue
            if atual is not None and atual.subsecoes:
                fechar()
                sub = max(atual.subsecoes, key=lambda s: _parecido(m.group(2) if m else it.texto, s.titulo))
                buf, pags = [], [it.pagina]
                continue
        elif it.tipo == "linha":
            buf.append(it.texto)
            pags.append(it.pagina)
    fechar()
    for cap in planta.capitulos:
        for p in (cap[1], *cap[1].subsecoes):
            if p.chave not in partes:
                avisos.append(f"sem corpo: {p.chave}")
                parte(p.chave, p.modulo)

    # ── anexos ──
    dados = {"fundacao": {"equipe": {}}, "qualidade": {}, "plano": {},
             "documentacao": {}}
    anexo, secao = None, ""
    texto_anx: dict = {}
    docs_anx: dict = {}
    pags_anx: dict = {}
    legenda_pendente = []          # tabelas esperando a legenda (testes)
    secao_doc_pags: list = []
    secao_doc_titulo = ""

    def fechar_documento():
        nonlocal secao_doc_pags, secao_doc_titulo
        if anexo and secao_doc_pags:
            docs_anx.setdefault(anexo.chave, []).append(
                {"titulo": secao_doc_titulo or anexo.titulo, "arquivo": arquivo,
                 "paginas": _paginas(secao_doc_pags), "fonte": fonte_doc})
        secao_doc_pags, secao_doc_titulo = [], ""

    for it in itens[fim:]:
        if it.tipo == "titulo":
            # O traço é obrigatório: sem ele, o divisor "ANEXOS" virava o
            # anexo S.
            m = re.match(r"^ANEXO\s*([A-Z])\s*[–-]\s*(.*)", _normal(it.texto))
            if m:
                fechar_documento()
                anexo = max(ppr.ANEXOS, key=lambda a: _parecido(m.group(2), a.titulo))
                if _parecido(m.group(2), anexo.titulo) < 0.6:
                    avisos.append(f"anexo {m.group(1)}: '{m.group(2)[:50]}' → {anexo.chave}?")
                secao = ""
                pags_anx.setdefault(anexo.chave, []).append(it.pagina)
                continue
            if anexo is None:
                continue
            fechar_documento()
            secao = re.sub(r"^\d+(\.\d+)*\s*", "", it.texto)
            if _SECAO_DOCUMENTO.search(secao):
                secao_doc_titulo = secao
            elif anexo.chave in ("equipamentos", "tps"):
                # O nome da máquina ("Acelerador Linear de Teleterapia") e o
                # do TPS ("Eclipse") são títulos, não texto.
                texto_anx.setdefault(anexo.chave, []).append(f"[[{secao}]]")
            continue
        if anexo is None:
            continue
        pags_anx[anexo.chave].append(it.pagina)
        if it.tipo == "embutida":
            if not secao_doc_titulo:
                secao_doc_titulo = secao or anexo.titulo
            secao_doc_pags.append(it.pagina)
            continue
        if secao_doc_titulo:
            # Texto e tabela de documento embutido que usa a fonte do PPR (o
            # contrato e os certificados da DUO) pertencem ao documento: lidos
            # como tabela do PPR, viravam "instrumentos" com cláusula de
            # pagamento no lugar do modelo.
            secao_doc_pags.append(it.pagina)
            continue
        if it.tipo == "tabela":
            regs = _registros(it.linhas)
            cab = " ".join(c or "" for c in (it.linhas[0] if it.linhas else []))
            tipo = _tipo_de_tabela(regs, cab, anexo.chave)
            if tipo == "testes":
                legenda_pendente.append(regs)
                continue
            _guardar(dados, tipo, regs)
            continue
        if re.match(r"^(Tabela|Figura)\s+[A-Z]\.\d+", it.texto):
            if legenda_pendente and it.texto.startswith("Tabela"):
                for regs in legenda_pendente:
                    chave, regs = _testes_da_legenda(it.texto, regs)
                    dados["qualidade"].setdefault(chave, []).extend(regs)
                legenda_pendente = []
            continue
        texto_anx.setdefault(anexo.chave, []).append(it.texto)
    fechar_documento()
    if legenda_pendente:
        avisos.append(f"{len(legenda_pendente)} tabela(s) de teste sem legenda")

    for anx in planta.anexos:
        a = anx[1]
        linhas = texto_anx.get(a.chave, [])
        if a.chave in ("equipamentos", "tps"):
            dados_rot = _itens_rotulados(linhas)
            if a.chave == "equipamentos":
                dados["qualidade"]["equipamentos"] = dados_rot
            else:
                dados["plano"]["sistemas_planejamento"] = dados_rot
            # O texto do anexo é só a introdução; o resto é dado do módulo.
            linhas = linhas[:next((i for i, l in enumerate(linhas)
                                   if l.startswith("[[") or "Fabricante:" in l),
                                  len(linhas))]
        texto = _sem_vide(_texto(linhas), planta)
        parte(f"anexo/{a.chave}", a.modulo, texto, docs_anx.get(a.chave, []),
              pags_anx.get(a.chave, []))
    # O SEVRRA mora dentro do H, mas é da Segurança.
    sevrra = [d for d in partes["anexo/gq"]["documentos"] if "SEVRRA" in _normal(d["titulo"])]
    partes["anexo/gq"]["documentos"] = [d for d in partes["anexo/gq"]["documentos"] if d not in sevrra]
    parte("anexo/gq_sevrra", ppr.SEVRRA.modulo, "", sevrra)

    dados["fundacao"]["instalacao"] = _instalacao(
        partes["identificacao"]["texto"], partes["objetivo"]["texto"],
        partes["classificacao"]["texto"])
    if "anexo/rejeitos" not in partes:
        parte("anexo/rejeitos", "qualidade")
    return {"clinica": CODIGO[clinica],
            "documento": {"arquivo": arquivo, "data": ""},
            "condicoes": sorted(condicoes), "partes": partes, "dados": dados,
            "avisos": avisos}


def _instalacao(identificacao: str, objetivo: str, classificacao: str) -> dict:
    """Os campos de ``instalacao`` (os mesmos do JSON da CEL) tirados dos três
    textos do corpo, que o molde escreve sempre do mesmo jeito. Campo que
    não casa fica vazio — nunca adivinhado."""
    def achar(padrao, texto):
        m = re.search(padrao, texto, re.S)
        return m.group(1).strip(" ,.") if m else ""
    return {
        "nome": achar(r"^O\s+(.+?)\s*\(N[úu]mero de matr[íi]cula", identificacao),
        "matricula_cnen": achar(r"matr[íi]cula CNEN\s+([\d.]+)", identificacao),
        "cnpj": achar(r"n[ºo°]\s*([\d./-]+)", identificacao),
        "endereco": achar(r"situado à\s+(.+?),\s*CEP", identificacao),
        "cep": achar(r"CEP\s+([\d.-]+)", identificacao),
        "telefone": achar(r"(?:contato|Contato):\s*([()\d\s-]+)", identificacao),
        "horario": achar(r"[ée] das\s+(.+?)\.\s*$", identificacao),
        "objetivo": achar(r"objetivo o\s+(.+?)\.?$", objetivo),
        "grupo": achar(r"GRUPO\s+([\w ]+?),", classificacao),
        "subgrupo": achar(r"SUBGRUPO\s+([\w ]+?)\.?$", classificacao),
    }


def _itens_rotulados(linhas: list) -> list:
    """Equipamentos e TPS vêm em "Rótulo: valor" sob um título com o nome.
    A taxa de dose continua em tópicos depois do rótulo (uma por energia), e
    vai junto, separada por "; "."""
    itens, nome, corpo, anterior = [], "", [], ""

    def fechar():
        if corpo:
            reg = _rotulados(" ".join(corpo))
            if reg:
                itens.append({"nome": nome, **reg})

    for l in linhas:
        if l.startswith("[[") and l.endswith("]]"):
            fechar()
            nome, corpo = l[2:-2], []
        elif "Fabricante:" in l:
            fechar()
            # Sem título próprio, o nome é a linha curta logo antes
            # ("Acelerador Linear de Teleterapia", "Eclipse"), em negrito.
            antes, _, depois = l.partition("Fabricante:")
            if antes.strip():
                nome = antes.strip()
            elif "Nome Comercial:" in anterior:
                # BET: "Bloco J.1 - Sistema 1 Nome Comercial: Eclipse".
                nome = anterior.split("Nome Comercial:", 1)[1].strip()
            elif anterior and len(anterior) < 60 and not anterior.endswith(":"):
                nome = anterior
            corpo = ["Fabricante:" + depois]
        elif corpo:
            corpo.append(l.lstrip("•- ").strip())
        anterior = l
    fechar()
    for reg in itens:
        reg["nome"] = re.sub(r"^Bloco [A-Z]\.\d+\s*-\s*", "", reg.get("nome", ""))
        if "taxa_dose" in reg:
            reg["taxa_dose"] = re.sub(r"\s*[•]\s*", "; ", reg["taxa_dose"]).strip("; ")
    return itens


def _guardar(dados: dict, tipo: str, regs: list) -> None:
    if tipo in ("medicos", "fisicos", "tecnicos", "enfermagem", "demais"):
        dados["fundacao"]["equipe"].setdefault(tipo, []).extend(regs)
    elif tipo == "asos":
        dados["documentacao"].setdefault("asos", []).extend(regs)
    else:
        dados["qualidade"].setdefault(tipo, []).extend(regs)


# ── Resumo sem conteúdo ──────────────────────────────────────────────────────

def resumo(s: dict) -> str:
    """Contagens: quantas partes com texto, quantos documentos, quantos
    faltando no disco. Nenhum valor do PPR."""
    linhas = [f"clínica {s['clinica']}  condições {s['condicoes']}"]
    for chave, parte in s["partes"].items():
        faltam = sum(1 for d in parte["documentos"] if d.get("falta"))
        linhas.append(
            f"  {chave:34} {parte['modulo']:12} texto {len(parte['texto']):5} car."
            f"  docs {len(parte['documentos'])}" + (f"  FALTAM {faltam}" if faltam else ""))
    for modulo, dados in s["dados"].items():
        contagem = ", ".join(f"{k} {len(v)}" for k, v in dados.items())
        linhas.append(f"  dados {modulo}: {contagem}")
    return "\n".join(linhas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clinica", choices=sorted(CODIGO))
    ap.add_argument("--anexos", type=Path,
                    default=Path.home() / "Downloads" / "PPR" / "anexos" / "PDFs",
                    help="pasta anexos/PDFs do projeto do PPR (só CEL)")
    a = ap.parse_args(argv)
    pasta_ppr = RAIZ_SERVICO / a.clinica / "ppr"
    if a.clinica == "CEL":
        copiar_anexos_cel(a.anexos, pasta_ppr)
        json_path = next((pasta_ppr / "fonte").glob("PPR_*.json"))
        s = semente_cel(json_path, pasta_ppr)
    else:
        s = semente_pdf(next((pasta_ppr / "fonte").glob("PPR_*.pdf")), a.clinica,
                        pasta_ppr)
    (pasta_ppr / "semente.json").write_text(
        json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    print(resumo(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
