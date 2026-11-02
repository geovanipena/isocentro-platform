"""Gera o Mapa do Conhecimento (HTML) a partir da base versionada.

Uso: python gerar_mapa.py <raiz isocentro>
Lê:   conhecimento/matriz/*.csv|json, conhecimento/fichas (cabeçalhos), referencias/CATALOGO.md,
      codigo-externo/CATALOGO.md e o modelo conhecimento/mapa/modelo.html
Gera: conhecimento/mapa/mapa-conhecimento.html

Tudo o que é derivado (o que está no acervo, fila de leitura, itens já adquiridos, cadeia de
sustentação, periodicidade e técnica dos requisitos) é recalculado aqui; não editar o HTML.
"""
import csv, datetime, glob, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gerar_matriz import cabecalho, lista, no_isocentro, situacao_isocentro  # noqa: E402

R = os.path.abspath(sys.argv[1])
K = os.path.join(R, "conhecimento")
M = os.path.join(K, "matriz")
HOJE = datetime.date.today().strftime("%d/%m/%Y")


def ler_csv(nome):
    return list(csv.DictReader(open(os.path.join(M, nome), encoding="utf-8"), delimiter=";"))


def ler_json(nome):
    return json.load(open(os.path.join(M, nome), encoding="utf-8"))


# ---------- acervo ----------
def catalogo_referencias():
    acervo, superadas, pasta = {}, set(), None
    for ln in open(os.path.join(R, "referencias", "CATALOGO.md"), encoding="utf-8"):
        if ln.startswith("## "):
            pasta = ln[3:].strip()
        m = re.match(r"\| \[([^\]]+)\]\(<[^>]+>\) \| ([^|]*) \|", ln)
        if m and pasta:
            if pasta.startswith("_"):
                superadas.add(m.group(1))
            else:
                acervo[m.group(1)] = {"t": m.group(2).strip(), "pasta": pasta}
    # Documentos internos (POPs) saíram de referencias/ para servico/ (P6, 22/10/2026);
    # no Mapa continuam no grupo de sempre.
    docs = os.path.join(R, "servico", "documentos.csv")
    if os.path.exists(docs):
        for d in csv.DictReader(open(docs, encoding="utf-8"), delimiter=";"):
            acervo[d["codigo"]] = {"t": d["titulo"], "pasta": "10 POPs CLINICA"}
    return acervo, superadas


def catalogo_codigo():
    repos, pasta = {}, None
    for ln in open(os.path.join(R, "codigo-externo", "CATALOGO.md"), encoding="utf-8"):
        if ln.startswith("## "):
            pasta = ln[3:].strip()
        m = re.match(r"\| \[([^\]]+)\]\(([^)]+)\) \| (.*?) \| ([^|]*) \| ([^|]*) \| ([^|]*) \|", ln)
        if m and pasta:
            repos[m.group(1)] = {"url": m.group(2), "desc": m.group(3).strip(), "licenca": m.group(4).strip(),
                                 "estrelas": m.group(5).strip(), "push": m.group(6).strip(), "pasta": pasta}
    return repos


# ---------- classificação ----------
def tipo_fonte(t, c):
    if t == "manual": return "man"
    if t == "codigo": return "cod"
    if t == "pop" or re.match(r"(POP-|LISTA-VERIF|PPR-CLINICA)", c): return "pop"
    if re.search(r"Release-Note|IFU|Guide", c, re.I): return "man"
    if re.match(r"(NN-|RDC-|NR-|LEI-|LGPD|CFM-|SAES-|GUIA-CNEN|ROTEIRO-VISA|RES-ANPD|RES-ANSN|CNEN-|NT-GVIMS|ANVISA-|ANPD-|AGENDA-ANSN)", c): return "norma"
    if re.match(r"(IAEA-(BIALYSTOK|COSTA|PANAMA|SRS-17)|IGAS-|IRSN-|SCOT-|UKHSA-)", c): return "inc"
    if re.match(r"(QUANTEC|HYTEC|ASTRO-|ESTRO-(REIRR|EANO)|RECOG|REIRR-|UK-SABR|ABS-|GEC-ESTRO|ACROP|EMBRACE|TIMMERMAN|CORSAIR|PENTEC|RCR-|ABFM-|EMAMI|HAIE-MEDER|POTTER|KAMRAVA|GRIMM)", c): return "cons"
    if re.match(r"(TG-|MPPG|TRS-|TECDOC|IAEA-|ICRU|IEC-|ISO-|DICOM|NCS-|IPEM|ICRP-|FDA-|IMDRF|WHO-|GSR|SSG-|SRS-47|NCRP|QUATRO|AAPM-|WGTG51|PQRT-|ESTRO-BOOKLET|CPQR|SAFER-RT|SNA-|UK-RT-|HEBD|CLRP|IHE-)", c): return "prot"
    return "lit"


PERIODOS = [("Diária", r"di[áa]ri|todo dia|dias de tratamento|dia do procedimento"),
            ("Semanal", r"seman"),
            ("Mensal", r"mens|m[êe]s"),
            ("Trimestral", r"trimest"),
            ("Semestral", r"semest"),
            ("Anual", r"anual|\bano\b"),
            ("Bienal", r"bienal|2 anos|24 meses|≤ ?2 anos"),
            ("5 anos ou mais", r"\b(5|10|20) anos"),
            ("Por paciente ou plano", r"plano|fra[çc][ãa]o|caso|estrutura|qa de paciente|cada qa|paciente|leitura"),
            ("Por evento ou mudança", r"comission|aceita|troca|vers[ãa]o|upgrade|servi[çc]o|mudan|incidente|antes d|instala|projeto|licenci|evento|calibra[çc][ãa]o|uso|fonte|submiss|fun[çc][ãa]o|interrup|habilitar|revis[ãa]o inicial|aquisi"),
            ("Contínua", r"cont[íi]nu|permanente|reten|em vigor"),
            ("Sem prazo definido", r".*")]

TECNICAS = [("SRS/SBRT", r"\bsrs\b|sbrt|sabr|estereot|radiocirurg|winston|campos? pequen|\bcone|TG-101|HYTEC|MPPG-9|ICRU-91|TRS-483|TG-155|UK-SABR|ABFM-SRS", ["A17", "C07", "I02"]),
            ("IMRT/VMAT", r"imrt|vmat|modula|\bmlc\b|TG-218|TG-119|TG-120|gam[am]a|flu[êe]ncia|ICRU-83", ["C06"]),
            ("Braquiterapia HDR", r"\bhdr\b|braqui|ir-192|aplicador|TG-43|TG-56|TG-59|MPPG-HDR|HEBD|TG-186|PQRT-CALIB", ["E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "H02"]),
            ("Elétrons", r"el[ée]tron", []),
            ("Ortovoltagem", r"ortovolt|\bkv\b.*(tubo|feixe)|TG-61|dermopan|baixa energia", ["A20"]),
            ("Imagem e IGRT", r"cbct|igrt|epid|imagem|tc de simula|ct-sim|TG-179|MPPG-IGRT|TG-66|MPPG-CT|portal", ["A08", "A19", "C08", "A09", "C02"])]


# etapas de gestão: sem código ligado, a ferramenta não se aplica
SEM_FERRAMENTA = {"Proteção radiológica e licenciamento", "Qualidade, risco e segurança do paciente",
                  "Acompanhamento e fim de tratamento"}


def periodo(q):
    q = (q or "").lower()
    for nome, rx in PERIODOS:
        if re.search(rx, q):
            return nome


def tecnicas(r):
    txt = " ".join([r["parametro"], r["valor"], r["periodicidade"], r["fonte"]])
    ts = [n for n, rx, acts in TECNICAS if re.search(rx, txt, re.I) or r["atividade"] in acts]
    return ts or ["Geral"]


def main():
    acervo, superadas = catalogo_referencias()
    al = ler_json("aliases.json")
    alias = al["aliases"]
    alvo_para_codigo = {}
    for c, outros in alias.items():
        for o in outros:
            alvo_para_codigo[o] = c

    def no_acervo(c):
        c2 = c if c in acervo else alvo_para_codigo.get(c, c)
        return c2 if c2 in acervo else None

    # ---------- atividades e vínculos ----------
    ativ_csv = list(csv.DictReader(open(os.path.join(M, "atividades.csv"), encoding="utf-8"), delimiter=";"))
    meta, ficha_de = {}, {}
    for f in sorted(glob.glob(os.path.join(K, "fichas", "atividades", "*.md"))):
        c = cabecalho(f)
        for i in lista(c.get("id")):
            meta[i] = c
            ficha_de[i] = os.path.basename(f)
    atividades = []
    for a in ativ_csv:
        m = meta.get(a["id"], {})
        cl = m.get("clinicas", "")
        atividades.append({"id": a["id"], "area": a["area"], "nome": a["atividade"], "nivel": a["nivel"],
                           "gatilho": a["gatilho"], "origem": a["origem"], "ficha": ficha_de.get(a["id"], ""),
                           "isocentro": situacao_isocentro(m, a["id"]),
                           "lacuna": str(m.get("lacuna_ppr", "")),
                           "clinicas": "[" + ", ".join(cl) + "]" if isinstance(cl, list) else str(cl),
                           "cod_iso": no_isocentro(m, a["id"], "codigo_isocentro"),
                           "tes_iso": no_isocentro(m, a["id"], "testes_isocentro")})
    byA = {a["id"]: a for a in atividades}

    fichas_ref = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(K, "fichas", "referencias", "*.md"))}
    fichas_cod = {os.path.splitext(os.path.basename(f))[0].replace("__", "/") for f in glob.glob(os.path.join(K, "fichas", "codigo", "*.md"))}
    fichas_man = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(K, "fichas", "manuais", "*.md"))}
    vinc, vistos = [], set()
    for v in ler_csv("vinculos.csv"):
        k = (v["atividade"], v["tipo"], v["alvo"])
        if k in vistos or v["atividade"] not in byA:
            continue
        vistos.add(k)
        a, t, alvo = k
        if t == "referencia":
            c = no_acervo(alvo)
            g, ficha = (acervo[c]["pasta"] if c else "(fora do acervo)"), alvo in fichas_ref
        elif t == "manual":
            g, ficha = "Manuais", alvo in fichas_man
        elif t == "codigo":
            g, ficha = "Código externo", alvo in fichas_cod
        else:
            g, ficha = "10 POPs CLINICA", False
        vinc.append({"a": a, "t": t, "alvo": alvo, "g": g, "ficha": ficha})

    # ---------- requisitos, conflitos, vigência, aquisição ----------
    reqs = []
    for r in ler_csv("requisitos.csv"):
        reqs.append({"id": r["id"], "a": r["atividade"], "p": r["parametro"], "v": r["valor"], "q": r["periodicidade"],
                     "n": r["nivel"], "f": r["fonte"], "l": r["local"], "o": r["nota"], "ac": bool(no_acervo(r["fonte"])),
                     "per": periodo(r["periodicidade"]), "tec": tecnicas(r)})
    conflitos = [{"id": c["id"], "tema": c["tema"], "fontes": c["fontes"], "d": c["descricao"], "as": c["atividades"],
                  "regra": c.get("regra_adotada", "pendente"), "prop": c.get("regra_proposta", ""),
                  "crit": c.get("criterio", ""), "quem": c.get("decide", "fisico")} for c in ler_json("conflitos.json")]
    vig = []
    for v in ler_json("vigencia.json"):
        c = v["codigo"]
        if c in acervo:
            ac, pasta = True, acervo[c]["pasta"][:2]
        elif c in superadas:
            ac, pasta = True, "_superadas"
        elif no_acervo(c):
            ac, pasta = True, acervo[no_acervo(c)]["pasta"][:2]
        else:
            ac, pasta = False, ""
        vig.append({"c": c, "s": v["situacao"], "d": v["descricao"], "u": v["url"], "ac": ac, "pasta": pasta, "alt": v["outras_frentes"]})
    vig_por = {v["c"]: v for v in vig}
    cand_todos = ler_json("aquisicao.json")
    candidatos = []
    for c in cand_todos:
        if no_acervo(c["codigo"]):
            continue
        links = c["links"]
        candidatos.append({"c": c["codigo"], "t": c["titulo"], "org": c["orgao"], "ano": c["ano"], "tipo": c["tipo"],
                           "pasta": c["pasta"], "as": c["atividades"], "ac": c["acesso"], "pr": c["prioridade"],
                           "sub": c["substitui"], "j": c["justificativa"], "u": links[0]["url"] if links else "",
                           "us": [{"r": l["rotulo"], "u": l["url"]} for l in links]})

    # ---------- fila de leitura ----------
    cand_as = {c["codigo"]: c["atividades"] for c in cand_todos}
    citados = {v["alvo"] for v in vinc} | {r["f"] for r in reqs}
    lido = lambda n: n in citados or any(x.startswith(n + " ") for x in citados)
    fila = []
    for c, d in acervo.items():
        nomes = [c] + alias.get(c, [])
        if any(lido(n) for n in nomes):
            continue
        acts = set(al["atividades_extra"].get(c, []))
        for n in nomes + ([al["parciais"][c]] if c in al["parciais"] and isinstance(al["parciais"][c], str) else []):
            acts |= set(cand_as.get(n, []))
        fila.append({"c": c, "t": d["t"], "pasta": d["pasta"], "as": sorted(a for a in acts if a in byA)})
    fila.sort(key=lambda d: (d["pasta"], d["c"]))
    nao_lidos = {d["c"] for d in fila}

    # ---------- código externo ----------
    repos = catalogo_codigo()
    cur = {r["repo"]: r for r in ler_csv("codigo.csv")}
    ativ_repo = defaultdict(set)
    for v in vinc:
        if v["t"] == "codigo":
            ativ_repo[v["alvo"]].add(v["a"])
    codigo = []
    for nome, r in repos.items():
        c = cur.get(nome, {})
        lic = r["licenca"]
        uso = "sem-licenca" if lic.lower().startswith("sem") else "copyleft" if re.match(r"(A?GPL|LGPL|MPL)", lic) else "a-confirmar" if lic == "NOASSERTION" else "livre"
        codigo.append({"repo": nome, "url": r["url"], "pasta": r["pasta"], "desc": r["desc"], "licenca": lic, "uso": uso,
                       "estrelas": r["estrelas"], "push": r["push"], "as": sorted(ativ_repo.get(nome, [])),
                       "implementa": c.get("implementa", ""), "conf": c.get("conformidade", "") or "nao-avaliada",
                       "div": [x for x in c.get("atividades_divergentes", "").split(",") if x], "nota": c.get("nota", "")})
    codigo.sort(key=lambda x: (-len(x["as"]), x["repo"]))
    div_de = defaultdict(list)
    for x in codigo:
        for a in x["div"]:
            div_de[a].append(x["repo"])

    # ---------- cadeia de sustentação por atividade ----------
    pend = defaultdict(list)
    for c in conflitos:
        if c["regra"] == "pendente":
            for a in c["as"]:
                pend[a].append(c["id"])
    refs = defaultdict(lambda: defaultdict(set))   # a -> tipo -> {docs lidos}
    for v in vinc:
        if v["t"] == "referencia" and v["g"] != "(fora do acervo)":
            refs[v["a"]][tipo_fonte("referencia", v["alvo"])].add(v["alvo"])
        elif v["t"] in ("pop", "manual", "codigo"):
            refs[v["a"]][tipo_fonte(v["t"], v["alvo"])].add(v["alvo"])
    req_de = defaultdict(list)
    for r in reqs:
        req_de[r["a"]].append(r)
        if r["ac"]:
            refs[r["a"]][tipo_fonte("referencia", r["f"])].add(r["f"])
    unread = defaultdict(lambda: defaultdict(set))
    for d in fila:
        for a in d["as"]:
            unread[a][tipo_fonte("referencia", d["c"])].add(d["c"])

    def elo(st, txt):
        return {"s": st, "d": txt}

    etapa_de = {x: e["nome"] for e in ler_json("etapas.json")["etapas"] for x in e["atividades"]}
    elos = {}
    for a in atividades:
        i, rf, un = a["id"], refs[a["id"]], unread[a["id"]]
        obrig = "OBRIG" in a["nivel"]
        if rf["norma"]:
            obr = elo("ok", ", ".join(sorted(rf["norma"])))
        elif un["norma"]:
            obr = elo("parcial", "No acervo, ainda não lida: " + ", ".join(sorted(un["norma"])))
        else:
            obr = elo("vazio", "Atividade obrigatória sem norma brasileira ligada") if obrig else elo("na", "Atividade de recomendação ou prática")
        met = rf["prot"] | rf["cons"]
        vivos = {d for d in met if vig_por.get(d, {}).get("s") != "substituido"}
        if vivos:
            mtd = elo("ok", ", ".join(sorted(vivos)))
        elif met:
            mtd = elo("diverge", "Só documento substituído: " + ", ".join(sorted(met)))
        elif un["prot"] | un["cons"]:
            mtd = elo("parcial", "No acervo, ainda não lido: " + ", ".join(sorted(un["prot"] | un["cons"])))
        else:
            mtd = elo("vazio", "Sem protocolo técnico nem consenso")
        rs = req_de[i]
        if not rs:
            val = elo("vazio", "Nenhum requisito numérico rastreado")
        elif pend[i]:
            val = elo("diverge", f"{len(rs)} requisito(s); conflito entre fontes pendente: " + ", ".join(pend[i]))
        elif not any(r["ac"] for r in rs):
            val = elo("parcial", f"{len(rs)} requisito(s), todos de fonte fora do acervo")
        else:
            val = elo("ok", f"{len(rs)} requisito(s) rastreado(s)")
        pop = elo("ok", ", ".join(sorted(rf["pop"]))) if rf["pop"] else elo("vazio", "Sem POP do serviço ligado")
        if div_de.get(i):
            fer = elo("diverge", "Diverge da norma vigente: " + ", ".join(div_de[i]))
        elif rf["cod"]:
            fer = elo("ok", ", ".join(sorted(rf["cod"])))
        elif etapa_de.get(i) in SEM_FERRAMENTA:
            fer = elo("na", "Atividade de gestão: não depende de código que mede ou calcula")
        else:
            fer = elo("vazio", "Sem ferramenta de código ligada")
        iso = a["isocentro"]
        reg = {"sim": elo("ok", "Coberto pelo ISOCENTRO"), "candidato": elo("parcial", "Candidato a módulo do ISOCENTRO"),
               "nao-se-aplica": elo("na", "Fora do escopo do ISOCENTRO")}.get(iso, elo("vazio", "Sem registro definido"))
        elos[i] = {"obr": obr, "met": mtd, "val": val, "pop": pop, "fer": fer, "reg": reg}

    # ---------- genealogia ----------
    gen = ler_csv("genealogia.csv")
    nos = {}
    for g in gen:
        for c in (g["de"], g["para"]):
            if c in nos:
                continue
            if c in acervo or no_acervo(c):
                st = "nao-lido" if (no_acervo(c) or c) in nao_lidos else "acervo"
            elif c in superadas:
                st = "superada"
            else:
                st = "fora"
            nos[c] = {"st": st, "vig": vig_por.get(c, {}).get("s", ""), "pasta": (acervo.get(no_acervo(c) or "", {}) or {}).get("pasta", "")}

    inc = ler_json("incidentes.json")
    etapas = ler_json("etapas.json")["etapas"]
    D = {"atividades": atividades, "vinculos": vinc, "gerado": HOJE}
    D2 = {"requisitos": reqs, "conflitos": conflitos, "vigencia": vig, "candidatos": candidatos, "gerado2": HOJE}
    D3 = {"acervo": len(acervo), "fila": fila}
    D4 = {"etapas": etapas, "elos": elos, "genealogia": gen, "nos": nos, "incidentes": inc["incidentes"],
          "sinteses": inc["sinteses"], "codigo": codigo, "periodos": [p for p, _ in PERIODOS],
          "tecnicas": [t for t, _, _ in TECNICAS] + ["Geral"], "gerado": HOJE}

    dados = "\n".join(f"const {n} = {json.dumps(o, ensure_ascii=False)};" for n, o in
                      (("D", D), ("D2", D2), ("D3", D3), ("D4", D4)))
    modelo = open(os.path.join(K, "mapa", "modelo.html"), encoding="utf-8").read()
    assert modelo.count("/*@DADOS@*/") == 1
    out = os.path.join(K, "mapa", "mapa-conhecimento.html")
    open(out, "w", encoding="utf-8", newline="\n").write(modelo.replace("/*@DADOS@*/", dados))
    # Versão para publicar no artefato: página pequena + dados.js à parte. Atualizar o
    # Mapa publicado troca só o dados.js, sem precisar ler a página inteira de volta.
    pub = os.path.join(K, "mapa", "publicar")
    os.makedirs(pub, exist_ok=True)
    assert modelo.count("<script>\n/*@DADOS@*/") == 1
    open(os.path.join(pub, "index.html"), "w", encoding="utf-8", newline="\n").write(
        modelo.replace("<script>\n/*@DADOS@*/", '<script src="dados.js"></script>\n<script>'))
    open(os.path.join(pub, "dados.js"), "w", encoding="utf-8", newline="\n").write(dados + "\n")
    print(f"{len(atividades)} atividades, {len(vinc)} vínculos, {len(reqs)} requisitos, {len(candidatos)} a adquirir, "
          f"{len(fila)} sem leitura de {len(acervo)}, {len(codigo)} repositórios -> {out}")


if __name__ == "__main__":
    main()
