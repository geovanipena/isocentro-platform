"""Gera itens-nivel2.csv a partir das tabelas extraídas (JATS) e das linhas transcritas do TRS-398 Rev. 1 e do adendo TG-51.

Uso: python -I itens_nivel2.py tabelas_mppg.csv saida.csv
"""
import csv, re, sys

SRC = {
    "MPPG8b": ("AAPM MPPG 8.b", "2023", "PMC10647991", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10647991/"),
    "MPPG2b": ("AAPM MPPG 2.b", "2021", "PMC8425868", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8425868/"),
    "MPPG5b": ("AAPM MPPG 5.b", "2022", "PMC9512346", "https://pmc.ncbi.nlm.nih.gov/articles/PMC9512346/"),
    "MPPG9b": ("AAPM-RSS MPPG 9.b", "2025", "PMC11969102", "https://pmc.ncbi.nlm.nih.gov/articles/PMC11969102/"),
    "MPPG11a": ("AAPM MPPG 11.a", "2021", "PMC8425907", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8425907/"),
}
TRS = ("IAEA TRS-398 Rev. 1", "2024", "https://www-pub.iaea.org/MTCD/publications/PDF/p15048-DOC-010-398-Rev1_web.pdf")
TG51A = ("AAPM TG-51 adendo (fótons)", "2014", "https://www.aapm.org/pubs/reports/RPT_67_Addendum.pdf")

COLS = ["item_id", "lote", "obrigacao", "protocolo", "versao_ano", "tabela_secao", "pagina_pdf", "item_doc",
        "teste", "aplicabilidade", "frequencia", "limite", "tipo_limite", "nota_rodape", "url", "status", "observacao"]

rows_out = []


def add(**kw):
    r = {c: "—" for c in COLS}
    r.update({k: (v if v not in ("", None) else "—") for k, v in kw.items()})
    rows_out.append(r)


def load(path):
    tabs = {}
    for x in csv.DictReader(open(path, encoding="utf-8"), delimiter=";"):
        k = (x["doc"], x["tabela"].strip())
        t = tabs.setdefault(k, {"rows": [], "notas": ""})
        t["rows"].append(x["celulas"].split(" ¦ "))
        if x["notas"]:
            t["notas"] = x["notas"]
    return tabs


def notes_map(notas):
    m = {}
    for part in notas.split(" | "):
        mm = re.match(r"^([a-z])\s+(.*)", part.strip())
        if mm:
            m[mm.group(1)] = mm.group(2)
    return m


def strip_marker(s, nm):
    """Separa marcador de nota de rodapé ('Daily a') e referência numérica ('constancy 7')."""
    found = []
    mm = re.search(r"\s([a-c])$", s)
    if mm and mm.group(1) in nm:
        found.append(f"{mm.group(1)}: {nm[mm.group(1)]}")
        s = s[: mm.start()]
    s = re.sub(r"\s\d{1,3}(?=\s*$|\s\()", "", s)  # referência bibliográfica numerada
    return s.strip(), found


def src(doc):
    p, v, pmc, url = SRC[doc]
    return p, v, url


# ---------- MPPG 8.b: Tabelas 3 a 8 (lote 1) ----------
def mppg8b(tabs):
    p, v, url = src("MPPG8b")
    for lab in ["TABLE 3", "TABLE 4", "TABLE 5", "TABLE 6", "TABLE 7", "TABLE 8"]:
        t = tabs[("MPPG8b", lab)]
        nm = notes_map(t["notas"])
        item = test = ""
        for r in t["rows"][1:]:
            r = (r + [""] * 4)[:4]
            item = r[0] or item
            if r[1]:
                test, f1 = strip_marker(r[1], nm)
            else:
                f1 = []
            freq, f2 = strip_marker(r[2], nm)
            lim, f3 = strip_marker(r[3], nm)
            freq = freq or rows_out[-1]["frequencia"]
            obr, obs, apl = "A07", "", "Acelerador linear"
            if item.startswith("S"):
                obr = "A14" if freq.lower().startswith("daily") else "A07"
            if item == "M1":
                obr = "A10"
            if item == "D1" and freq.lower().startswith("daily"):
                obr, obs = "A07;A13", "NN 6.10 art. 35, II exige teste diário do fator de calibração"
            if item == "D1" and freq.lower().startswith("monthly"):
                obr, obs = "A07;A15", "Constância contra baseline do dispositivo; NN 6.10 art. 35, IV pede dose absorvida na água em condições de referência — não equivalente"
            if item == "D1" and freq.lower().startswith("annual"):
                obs = 'Original: "1% of nominal TG-51 output"; por decisão do usuário, aplicar como 1% da saída nominal pelo protocolo do PPR (TRS-398 Rev. 1)'
            if item == "M14":
                apl = "Mesa robótica (6DoF)"
            if item == "W2":
                apl = "Filtro físico, se usado"
            if item.startswith("W") and item != "W2":
                apl = "Filtro eletrônico/dinâmico"
            if item == "D13":
                apl = "TBI/TSET, se usado"
            add(lote=1, obrigacao=obr, protocolo=p, versao_ano=v, tabela_secao=lab.title(), item_doc=item, teste=test,
                aplicabilidade=apl, frequencia=freq, limite=lim, tipo_limite="nível de ação",
                nota_rodape=" / ".join(f1 + f2 + f3), url=url, status="TRANSCRITO (XML PMC)", observacao=obs)


# ---------- MPPG 9.b: Tabela 1 (braço C) ----------
def mppg9b(tabs):
    p, v, url = src("MPPG9b")
    t = tabs[("MPPG9b", "TABLE 1")]
    freq = ""
    for r in t["rows"][1:]:
        r = (r + [""] * 3)[:3]
        freq = r[0] or freq
        test, _ = strip_marker(r[1], {})
        add(lote=5, obrigacao="C07;A07", protocolo=p, versao_ano=v, tabela_secao="Table 1", teste=test,
            aplicabilidade="SRS/SBRT em linac braço C", frequencia=freq, limite=r[2], tipo_limite="nível de ação",
            nota_rodape="Action limits are absolute accuracy, not variation from baseline, unless otherwise stated.",
            url=url, status="TRANSCRITO (XML PMC)")


# ---------- MPPG 2.b: Tabela 1 (IGRT) ----------
def mppg2b(tabs):
    p, v, url = src("MPPG2b")
    t = tabs[("MPPG2b", "TABLE 1")]
    freq, sub = "Aceitação e comissionamento", ""
    for r in t["rows"][1:]:
        r = (r + [""] * 2)[:2]
        if r[0] == r[1] and r[0]:
            if r[0] in ("Imaging dose", "Image quality"):
                sub = r[0]
            elif r[0] in ("Routine quality assurance",):
                continue
            else:
                freq, sub = r[0], ""
            continue
        if r[0] == "Procedure":
            continue
        test = f"{sub}: {r[0]}" if sub else r[0]
        add(lote=2, obrigacao="A08", protocolo=p, versao_ano=v, tabela_secao="Table 1", teste=test,
            aplicabilidade="IGRT por raios X (kV, MV, CBCT)", frequencia=freq, limite=r[1],
            tipo_limite="tolerância" if r[1] else "—", url=url, status="TRANSCRITO (XML PMC)")


# ---------- MPPG 5.b: tabela-resumo e Tabelas 4–10 (lote 4) ----------
def mppg5b(tabs):
    p, v, url = src("MPPG5b")
    spec = {"": ("Tabela-resumo das recomendações", [0, 1, None, 2]), "TABLE 4": ("Table 4", [0, 1, 2, 3]),
            "TABLE 5": ("Table 5", [0, 1, 2, None]), "TABLE 6": ("Table 6", [None, 1, 0, 2]),
            "TABLE 7": ("Table 7", [0, 1, 2, 3]), "TABLE 8": ("Table 8", [0, 1, 2, None]),
            "TABLE 9": ("Table 9", [None, 1, 0, 2]), "TABLE 10": ("Table 10", [0, 1, 2, 3])}
    for lab, (nome, (ci, ct, ce, cl)) in spec.items():
        t = tabs[("MPPG5b", lab)]
        prev = [""] * 5
        for r in t["rows"][1:]:
            r = (r + [""] * 5)[:5]
            r = [c or prev[i] if i in (0,) and lab in ("TABLE 6", "TABLE 9") else c for i, c in enumerate(r)]
            prev = r
            teste = r[ct]
            if ce is not None and r[ce]:
                teste = f"{teste} — {r[ce]}" if lab not in ("TABLE 6", "TABLE 9") else f"{r[ce]}: {teste}"
            lim = r[cl] if cl is not None else ("ver Table 6" if lab == "TABLE 5" else "ver Table 9")
            apl = "Elétrons" if lab == "TABLE 10" else ("IMRT/VMAT" if lab in ("TABLE 8", "TABLE 9") else "Fótons")
            if lab == "":
                apl = "TPS (fótons e elétrons)"
            add(lote=4, obrigacao="B01;B02", protocolo=p, versao_ano=v, tabela_secao=nome,
                item_doc=r[ci] if ci is not None else "", teste=teste, aplicabilidade=apl,
                frequencia="Comissionamento e após mudança relevante do TPS", limite=lim,
                tipo_limite="tolerância" if lim and not lim.startswith("ver") else "—", url=url,
                status="TRANSCRITO (XML PMC)",
                observacao="Frequência atribuída pelo escopo do MPPG 5.b (comissionamento/validação); conferir texto para QA de rotina")


# ---------- MPPG 11.a: checagens de plano e prontuário ----------
def mppg11a(tabs):
    p, v, url = src("MPPG11a")
    plano = {"TABLE 7": ("E03;C04", "Inicial (antes do 1º tratamento)", "Braquiterapia HDR; executa: físico"),
             "TABLE 8": ("C04", "Inicial (antes do 1º tratamento)", "Teleterapia; executa: físico"),
             "TABLE 9": ("C04", "Inicial (antes do 1º tratamento)", "Teleterapia; executa: técnico"),
             "TABLE 10": ("LACUNA", "Semanal", "Teleterapia; executa: físico"),
             "TABLE 11": ("D05", "Fim do tratamento", "Teleterapia"),
             "TABLE 13": ("E03", "Pré e pós-tratamento", "Braquiterapia HDR"),
             "TABLE 14": ("LACUNA", "Semanal", "Braquiterapia HDR")}
    for lab, (obr, freq, apl) in plano.items():
        t = tabs[("MPPG11a", lab)]
        head = t["rows"][0]
        secao_col = head[0] == "" or head[0] == "Sections"
        sec = ""
        for r in t["rows"][1:]:
            if secao_col:
                sec = r[0] or sec
                cells = r[1:]
            else:
                cells = r
            for i, c in enumerate(cells):
                if not c:
                    continue
                tipo = "recomendado" if i == 0 else "opcional"
                add(lote=5, obrigacao=obr, protocolo=p, versao_ano=v, tabela_secao=lab.title(),
                    item_doc=sec, teste=c, aplicabilidade=apl, frequencia=freq, limite="Verificado/conforme",
                    tipo_limite=tipo, url=url, status="TRANSCRITO (XML PMC)",
                    observacao="Checagem física semanal não está no catálogo v1 (lacuna já registrada)" if obr == "LACUNA" else "")


# ---------- TRS-398 Rev. 1 e adendo TG-51 (lote 3), transcritos do PDF ----------
def trs_tg51():
    p, v, url = TRS
    L = []
    for q, val in [("Phantom material", "Water"), ("Chamber type", "Cylindrical or plane parallel"),
                   ("Measurement depths", "20 g/cm2 and 10 g/cm2"), ("Source–chamber distance", "100 cm"),
                   ("Field size at source–chamber distance", "10 cm × 10 cm")]:
        L.append(("A03", "Table 14", "109-110", f"Qualidade do feixe de fótons (TPR20,10): {q}", "Fótons de alta energia", val))
    for q, val in [("Phantom material", "Water"), ("Chamber type", "Cylindrical"), ("Measurement depth, zref", "10 g/cm2"),
                   ("Source–surface distance or source–chamber distance", "100 cm (isocêntrico: usar a SAD do acelerador — nota a)"),
                   ("Field size", "10 cm × 10 cm")]:
        L.append(("A03", "Table 15", "111", f"Dose absorvida na água, fótons: {q}", "Fótons de alta energia", val))
    for q, val in [("Phantom material", "Water"), ("Chamber type", "For R50 > 3 g/cm2, plane parallel or cylindrical; For R50 < 3 g/cm2, plane parallel"),
                   ("Source–surface distance", "100 cm"), ("Field size at phantom surface", "At least 10 cm × 10 cm")]:
        L.append(("A03", "Table 18", "132", f"Qualidade do feixe de elétrons (R50): {q}", "Elétrons", val))
    for q, val in [("Phantom material", "Water"),
                   ("Chamber type", "For R50 [≥] 3 g/cm2, plane parallel or cylindrical; For R50 < 3 g/cm2, plane parallel"),
                   ("Measurement depth, zref", "0.6R50 - 0.1 g/cm2"), ("Source–surface distance", "100 cm"),
                   ("Field size at phantom surface", "10 cm × 10 cm")]:
        L.append(("A03", "Table 19", "134", f"Dose absorvida na água, elétrons: {q}", "Elétrons", val))
    for a in L:
        add(lote=3, obrigacao=a[0], protocolo=p, versao_ano=v, tabela_secao=a[1], pagina_pdf=a[2], teste=a[3],
            aplicabilidade=a[4], frequencia="Em cada calibração de referência", limite=a[5], tipo_limite="condição de referência",
            url=url, status="TRANSCRITO (PDF IAEA)",
            observacao="Símbolo ≥ perdido na extração do PDF; conferir na página" if "[≥]" in a[5] else "Protocolo primário do PPR")
    specs = [("Chamber settling", "equilibrium is reached in <5 min; the initial and equilibrium readings agree within 0.5%",
              "Should be less than a 0.5% change in chamber reading per monitor unit from beam-on for a warmed up machine, to stabilization"),
             ("Leakage", "<0.1% of the chamber reading", "< 0.1 % of chamber reading (0.999 < Pleak < 1.001)"),
             ("Polarity effect", "Less than 0.4% of the chamber reading; the polarity energy dependence is <0.3% between the energies of the 60Co beam and 10 MV photon beam",
              "< 0.4 % correction (0.996 < Ppol < 1.004); < 0.5 % maximum variation in Ppol with energy (total range)"),
             ("Initial recombination", "<0.2% at polarizing voltages of ~300 V", "less than 0.2%, that is, Cinit < 0.002, for the TG-51 reference conditions"),
             ("Recombination: opposite polarities", "difference in the initial recombination correction obtained with opposite polarities is <0.1%",
              "Difference in initial-recombination correction between opposite polarities should be less than 0.1%"),
             ("Recombination correction máxima", "If the correction exceeds 1.05, other methods have to be used", ""),
             ("Chamber stability", "Change in the calibration coefficient of <0.3% over a typical recalibration period of 2 years",
              "less than a 0.3% change in calibration coefficient over the typical recalibration period of 2 years")]
    for q, trs, tg in specs:
        add(lote=3, obrigacao="A04", protocolo=p, versao_ano=v, tabela_secao="Table 3", pagina_pdf="52",
            teste=f"Câmara classe de referência: {q}", aplicabilidade="Câmara de ionização de referência",
            frequencia="Na aquisição e após calibração", limite=trs, tipo_limite="especificação", url=url,
            status="TRANSCRITO (PDF IAEA)",
            observacao="CONFLITO com TG-51 adendo (variação de Ppol com energia: 0.3% Co-60→10 MV × 0.5% faixa total)" if q == "Polarity effect" else "")
        if tg:
            add(lote=3, obrigacao="A04", protocolo=TG51A[0], versao_ano=TG51A[1], tabela_secao="Table III", pagina_pdf="15",
                teste=f"Câmara classe de referência: {q}", aplicabilidade="Câmara de referência, fótons MV",
                frequencia="Na aquisição e após calibração", limite=tg, tipo_limite="especificação", url=TG51A[2],
                status="TRANSCRITO (PDF AAPM)", observacao="Checagem cruzada (TG-51 não é o protocolo do PPR); layout do PDF em colunas — conferir")
    add(lote=3, obrigacao="A04", protocolo=p, versao_ano=v, tabela_secao="§4.3", pagina_pdf="61",
        teste="Calibração da câmara de referência na qualidade Qo", aplicabilidade="Câmara de referência",
        frequencia="intervals not exceeding three years or whenever the user suspects that the chamber has been damaged",
        limite="—", tipo_limite="periodicidade", url=url, status="TRANSCRITO (PDF IAEA)",
        observacao="CONFLITO: NN 6.10 art. 49 p.u. I–II exige 2 anos — prevalece a norma brasileira")
    add(lote=3, obrigacao="A04", protocolo=p, versao_ano=v, tabela_secao="§4.3", pagina_pdf="61",
        teste="Recalibração para verificar a dependência com a qualidade (kQ,Qo medido)", aplicabilidade="Câmara com kQ,Qo medido",
        frequencia="at least every third time that the chamber is calibrated or every six years, whichever is shorter",
        limite="—", tipo_limite="periodicidade", url=url, status="TRANSCRITO (PDF IAEA)")
    add(lote=3, obrigacao="A06", protocolo=p, versao_ano=v, tabela_secao="§4.3", pagina_pdf="61",
        teste="Verificação de estabilidade antes e depois do envio ao laboratório de calibração", aplicabilidade="Sistema dosimétrico de referência",
        frequencia="before and after the calibration", limite="—", tipo_limite="—", url=url, status="TRANSCRITO (PDF IAEA)")
    add(lote=3, obrigacao="A05", protocolo=p, versao_ano=v, tabela_secao="§4.2 (e)", pagina_pdf="50",
        teste="Dispositivo de verificação de estabilidade (fonte-teste ou comparação entre dosímetros duplicados)", aplicabilidade="Sistema dosimétrico de referência",
        frequencia="regular", limite="—", tipo_limite="—", url=url, status="TRANSCRITO (PDF IAEA)",
        observacao="NN 6.10 art. 49 p.u. III fixa trimestral e ±1%")
    add(lote=3, obrigacao="A05", protocolo=p, versao_ano=v, tabela_secao="§4.4.2", pagina_pdf="67",
        teste="Verificar estabilidade de longo e curto prazo do dosímetro antes das medidas (fonte-teste ou comparação com pelo menos dois outros sistemas); pré-irradiar a câmara (10 Gy em geral suficiente)",
        aplicabilidade="Sistema dosimétrico de referência", frequencia="Before measurements are made", limite="—",
        tipo_limite="—", url=url, status="TRANSCRITO (PDF IAEA)")


# ---------- IAEA TECDOC-1274 (lote 6, HDR Ir-192), transcrito do PDF ----------
TEC = ("IAEA TECDOC-1274", "2002", "https://www-pub.iaea.org/MTCD/Publications/PDF/te_1274_prn.pdf")


def tecdoc():
    p, v, url = TEC
    L = [("E02", "§5.5", "21", "Constância da câmara poço", "at least 4 times per year",
          "within ±1% for high-energy photon sources", "recalibração recomendada se exceder"),
         ("E02", "§7.1.6", "36", "Leitura com fonte de verificação de meia-vida longa (137Cs ou 60Co) antes e depois de cada calibração da câmara poço e em intervalos regulares",
          "before and after any calibration; at regular intervals", "should remain constant to within ±0.5% (corrigida por T, P e decaimento)", "constância"),
         ("E02", "§7.1.6", "36", "Intervalo de recalibração da câmara poço usada para 192Ir com procedimento abreviado de QA",
          "shortened from 5 years to 2 years", "—", "periodicidade"),
         ("E02", "§9.2", "47", "Sensibilidade da câmara poço em função da profundidade de inserção da fonte (sweet spot)",
          "Na aceitação da câmara e quando houver mudança de inserto", "—", "—"),
         ("E03;E06", "§7.1.3", "35", "Medida da fonte HDR: no mínimo 5 leituras por inserção, pelo menos 2 inserções",
          "Em cada medida de fonte", "readings within 0.3% of the average reading and the average of two sets of readings within 0.5%", "tolerância"),
         ("E03;E06", "§9.1", "45", "Verificação independente, por físico qualificado, da intensidade da fonte declarada no certificado antes de usar no cálculo de dose",
          "A cada nova fonte", "—", "—")]
    for obr, sec, pag, teste, freq, lim, tipo in L:
        add(lote=6, obrigacao=obr, protocolo=p, versao_ano=v, tabela_secao=sec, pagina_pdf=pag, teste=teste,
            aplicabilidade="Braquiterapia HDR 192Ir (GammaMedplus)", frequencia=freq, limite=lim, tipo_limite=tipo,
            url=url, status="TRANSCRITO (PDF IAEA)",
            observacao="NN 6.10 art. 54 p.u. fixa a periodicidade legal; prevalece sobre o TECDOC" if pag in ("21", "36") else "")


tabs = load(sys.argv[1])
mppg8b(tabs); mppg2b(tabs); mppg9b(tabs); mppg5b(tabs); mppg11a(tabs); trs_tg51(); tecdoc()
for i, r in enumerate(rows_out, 1):
    if r["protocolo"] == "AAPM MPPG 8.b":
        for c in ("teste", "limite"):
            r[c] = re.sub(r"(\d)o\b", r"\1°", r[c])
    r["item_id"] = f"IT{i:04d}"
w = csv.DictWriter(open(sys.argv[2], "w", newline="", encoding="utf-8-sig"), fieldnames=COLS, delimiter=";")
w.writeheader(); w.writerows(rows_out)
from collections import Counter
print(len(rows_out), dict(Counter((r["lote"], r["protocolo"]) for r in rows_out)))
