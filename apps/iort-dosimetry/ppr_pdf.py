"""
ppr_pdf.py – Gerador de PDF fiel ao original LaTeX do PPR.

Design baseado na análise do PPR-universitario_Set_2025c.pdf:
  • Tipografia: Times-Roman / Times-Bold, corpo 12pt, justificado com recuo
  • Capítulos: número + TÍTULO EM MAIÚSCULAS, preto, sem decoração colorida
  • Seções: número + Título em bold Times
  • Sumário: links em azul (#1A237E) com pontos guia — idêntico ao LaTeX
  • Tabelas: bordas pretas simples, cabeçalho bold, sem cor de fundo
  • Cabeçalho/Rodapé: linha fina cinza, nome da instalação + "Plano de Proteção Radiológica"
  • PDFs externos: embeddados inline como imagens (pdftoppm) em cada seção
"""

import os, datetime, subprocess, tempfile, shutil
from copy import deepcopy
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
    NextPageTemplate, Image,
)
from reportlab.lib.colors import HexColor, black, white

try:
    from pypdf import PdfWriter, PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# ── Cores ────────────────────────────────────────────────────────────────────
AZUL  = HexColor("#1A237E")   # azul dos links do sumário (LaTeX padrão)
CINZA = HexColor("#666666")   # cabeçalho/rodapé
PRETO = black

# ── Dimensões ─────────────────────────────────────────────────────────────────
W, H   = A4
ML     = 3.0 * cm
MR     = 2.5 * cm
MT     = 3.0 * cm
MB     = 2.5 * cm
BODY_W = W - ML - MR


# ── PDF → Imagens ─────────────────────────────────────────────────────────────

def _pdf_to_images(pdf_path: str, tmpdir: str, dpi: int = 150) -> list:
    """Converte cada página de um PDF em JPEG dentro de tmpdir.
    Retorna lista de caminhos de imagem (strings) ou [] em caso de erro."""
    if not pdf_path or not os.path.exists(pdf_path):
        return []
    import hashlib
    h = hashlib.md5(pdf_path.encode()).hexdigest()[:10]
    prefix = os.path.join(tmpdir, f"p_{h}")
    try:
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", str(dpi), pdf_path, prefix],
            capture_output=True, timeout=180, check=False)
    except Exception:
        return []
    imgs = sorted(Path(tmpdir).glob(f"p_{h}-*.jpg")) + \
           sorted(Path(tmpdir).glob(f"p_{h}*.jpg"))
    seen = set(); result = []
    for p in imgs:
        if p not in seen:
            seen.add(p); result.append(str(p))
    return result


def _embed_pdf(pdf_path: str, tmpdir: str,
               max_w: float = None, max_h: float = None) -> list:
    """Retorna flowables (Images) com todas as páginas do PDF."""
    if max_w is None: max_w = BODY_W
    if max_h is None: max_h = H - MT - MB - 1.5 * cm
    imgs = _pdf_to_images(pdf_path, tmpdir)
    if not imgs:
        return [Paragraph(
            f"[PDF: {os.path.basename(pdf_path)}]",
            ParagraphStyle("_pfb", fontName="Times-Roman", fontSize=10,
                           textColor=CINZA, alignment=TA_CENTER))]
    flowables = []
    for ip in imgs:
        try:
            img = Image(ip)
            scale = min(max_w / img.drawWidth, max_h / img.drawHeight, 1.0)
            img.drawWidth  *= scale
            img.drawHeight *= scale
            img.hAlign = "CENTER"
            flowables.append(img)
            flowables.append(Spacer(1, 0.3 * cm))
        except Exception:
            pass
    return flowables


# ── Estilos ───────────────────────────────────────────────────────────────────

def _estilos():
    b = getSampleStyleSheet()
    def ad(name, **kw):
        if name not in b:
            b.add(ParagraphStyle(name=name, **kw))
        return b[name]

    # Corpo
    ad("P_N",  fontName="Times-Roman", fontSize=12, leading=18,
       alignment=TA_JUSTIFY, firstLineIndent=1.25*cm, spaceAfter=4)
    ad("P_N0", fontName="Times-Roman", fontSize=12, leading=18,
       alignment=TA_JUSTIFY, spaceAfter=4)
    ad("P_NL", fontName="Times-Roman", fontSize=12, leading=18,
       alignment=TA_LEFT, spaceAfter=4)

    # Capítulos e seções (PRETO — idêntico ao original)
    ad("P_Cap",  fontName="Times-Bold", fontSize=14, leading=20,
       spaceBefore=22, spaceAfter=10, textColor=PRETO)
    ad("P_Sec",  fontName="Times-Bold", fontSize=13, leading=18,
       spaceBefore=14, spaceAfter=7, textColor=PRETO)
    ad("P_Sub",  fontName="Times-Bold", fontSize=12, leading=16,
       spaceBefore=10, spaceAfter=5, textColor=PRETO)

    # Títulos de página e anexos (preto, centralizado)
    ad("P_PT",  fontName="Times-Bold", fontSize=16, leading=22,
       alignment=TA_CENTER, textColor=PRETO, spaceAfter=20)
    ad("P_AT",  fontName="Times-Bold", fontSize=14, leading=20,
       alignment=TA_CENTER, textColor=PRETO, spaceAfter=16)

    # Sumário — AZUL como no LaTeX original
    ad("P_TC",  fontName="Times-Bold",   fontSize=12, leading=16,
       textColor=AZUL, spaceAfter=3)
    ad("P_TS",  fontName="Times-Roman",  fontSize=12, leading=16,
       textColor=AZUL, spaceAfter=2, leftIndent=1.5*cm)
    ad("P_TA",  fontName="Times-Bold",   fontSize=12, leading=16,
       textColor=AZUL, spaceAfter=3)

    # Utilitários
    ad("P_Leg", fontName="Times-Roman", fontSize=11, leading=15,
       alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
    ad("P_Ref", fontName="Times-Roman", fontSize=12, leading=18,
       alignment=TA_JUSTIFY, spaceAfter=8,
       leftIndent=1.5*cm, firstLineIndent=-1.5*cm)
    ad("P_Blt", fontName="Times-Roman", fontSize=12, leading=18,
       alignment=TA_JUSTIFY, leftIndent=2.5*cm, firstLineIndent=-1.0*cm, spaceAfter=2)
    ad("P_Qt",  fontName="Times-Italic", fontSize=12, leading=17,
       alignment=TA_JUSTIFY, leftIndent=2.0*cm, rightIndent=1.0*cm,
       spaceAfter=6, spaceBefore=4)
    ad("P_As",  fontName="Times-Roman",  fontSize=12, leading=16, alignment=TA_CENTER)
    ad("P_Ac",  fontName="Times-Roman",  fontSize=11, leading=15, alignment=TA_CENTER)

    # Capa
    ad("P_CI",  fontName="Times-Bold", fontSize=12, leading=16,
       alignment=TA_CENTER, spaceAfter=2)
    ad("P_CT",  fontName="Times-Roman", fontSize=16, leading=22,
       alignment=TA_CENTER, spaceAfter=4)
    ad("P_CC",  fontName="Times-Bold", fontSize=12, leading=16,
       alignment=TA_CENTER, spaceAfter=2)

    return b


# ── Documento ─────────────────────────────────────────────────────────────────

class PPRDoc(BaseDocTemplate):
    def __init__(self, path, dados, **kw):
        super().__init__(path, **kw)
        self.dados = dados
        fc = Frame(ML, MB, BODY_W, H-MT-MB, id="capa")
        fp = Frame(ML, MB, BODY_W, H-MT-MB, id="pre")
        fb = Frame(ML, MB+0.9*cm, BODY_W, H-MT-MB-1.1*cm, id="corpo")
        self.addPageTemplates([
            PageTemplate(id="Capa",  frames=[fc], onPage=_cb_capa),
            PageTemplate(id="Pre",   frames=[fp], onPage=_cb_pre),
            PageTemplate(id="Corpo", frames=[fb], onPage=_cb_corpo),
        ])


def _cb_capa(canvas, doc): pass


def _cb_pre(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 11)
    canvas.setFillColor(CINZA)
    canvas.drawCentredString(W/2, MB-0.4*cm, str(doc.page))
    canvas.restoreState()


def _cb_corpo(canvas, doc):
    canvas.saveState()
    nome = doc.dados.get("instalacao", {}).get("nome", "")
    # Cabeçalho
    canvas.setStrokeColor(CINZA); canvas.setLineWidth(0.5)
    canvas.line(ML, H-MT+0.3*cm, W-MR, H-MT+0.3*cm)
    canvas.setFont("Times-Roman", 9); canvas.setFillColor(CINZA)
    canvas.drawString(ML, H-MT+0.55*cm, nome[:70])
    canvas.drawRightString(W-MR, H-MT+0.55*cm, "Plano de Proteção Radiológica")
    # Rodapé
    canvas.line(ML, MB-0.25*cm, W-MR, MB-0.25*cm)
    canvas.setFont("Times-Roman", 11)
    canvas.drawCentredString(W/2, MB-0.55*cm, str(doc.page))
    canvas.restoreState()


# ── Utilitários ───────────────────────────────────────────────────────────────

def _sp(n=1): return Spacer(1, n*0.5*cm)

def _cap(num, titulo, st):
    return [_sp(0.5),
            Paragraph(f"{num}  {titulo.upper()}", st["P_Cap"]),
            _sp(0.2)]

def _sec(num, titulo, st):
    return [Paragraph(f"{num}  {titulo}", st["P_Sec"])]

def _sub(num, titulo, st):
    return [Paragraph(f"{num}  {titulo}", st["P_Sub"])]

def _p(txt, st, ind=True):
    return Paragraph(txt, st["P_N" if ind else "P_N0"])

def _blt(txt, st):
    return Paragraph(f"• {txt}", st["P_Blt"])

def _vide(a, st):
    return Paragraph(f'Vide anexo <font color="{AZUL.hexval()}"><b>{a}</b></font>.', st["P_N"])

def _at(titulo, st):
    return [Paragraph(titulo, st["P_AT"]), _sp(0.3)]

def _assina(nome, extras, st):
    s = [HRFlowable(width="50%", thickness=0.8, color=PRETO,
                    hAlign="CENTER", spaceBefore=16, spaceAfter=3)]
    s.append(Paragraph(nome, st["P_As"]))
    for e in extras: s.append(Paragraph(e, st["P_Ac"]))
    s.append(_sp(0.5))
    return s


def _tabela(header, rows, widths, st, legenda=""):
    """Tabela com bordas pretas simples — idêntica ao original."""
    all_rows = [header] + rows
    t = Table(all_rows, colWidths=widths, repeatRows=1, splitByRow=True)
    t.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(-1,0),  "Times-Bold"),
        ("FONTSIZE",      (0,0),(-1,0),  12),
        ("LEADING",       (0,0),(-1,0),  16),
        ("FONTNAME",      (0,1),(-1,-1), "Times-Roman"),
        ("FONTSIZE",      (0,1),(-1,-1), 12),
        ("LEADING",       (0,1),(-1,-1), 16),
        ("ALIGN",         (0,0),(-1,-1), "LEFT"),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("GRID",          (0,0),(-1,-1), 0.5, PRETO),
        ("LINEABOVE",     (0,0),(-1,0),  1.0, PRETO),
        ("LINEBELOW",     (0,0),(-1,0),  1.0, PRETO),
        ("LINEBELOW",     (0,-1),(-1,-1),1.0, PRETO),
    ]))
    result = [t]
    if legenda: result.append(Paragraph(legenda, st["P_Leg"]))
    return result


def _embed_img(path, st, legenda="", max_w=None, max_h=None):
    """Embute uma imagem com dimensionamento seguro."""
    if not path or not os.path.exists(str(path)): return []
    if max_w is None: max_w = BODY_W
    if max_h is None: max_h = 16*cm
    try:
        img = Image(str(path))
        scale = min(max_w/img.drawWidth, max_h/img.drawHeight, 1.0)
        img.drawWidth *= scale; img.drawHeight *= scale
        img.hAlign = "CENTER"
        result = [img, _sp(0.2)]
        if legenda: result.append(Paragraph(legenda, st["P_Leg"]))
        return result
    except Exception:
        return []


def _toc_row(num, titulo, pg, st, sty="P_TC", indent=0, upper=False):
    txt = titulo.upper() if upper else titulo
    num_s = f"{num}  " if num else ""
    # Largura segura para o label
    lw = max(BODY_W - indent - 1.5*cm, 4*cm)
    pg_w = 1.5*cm

    lbl = Paragraph(
        f'<font color="{AZUL.hexval()}">{num_s}{txt}</font>', st[sty])
    pg_p = Paragraph(
        f'<font color="{AZUL.hexval()}">{pg}</font>',
        ParagraphStyle("_tp", fontName="Times-Roman", fontSize=12,
                       leading=16, alignment=TA_RIGHT, textColor=AZUL))
    t = Table([[lbl, pg_p]], colWidths=[lw, pg_w],
              style=TableStyle([
                  ("LEFTPADDING",   (0,0),(-1,-1), indent),
                  ("RIGHTPADDING",  (0,0),(-1,-1), 0),
                  ("TOPPADDING",    (0,0),(-1,-1), 1),
                  ("BOTTOMPADDING", (0,0),(-1,-1), 1),
                  ("VALIGN",        (0,0),(-1,-1), "TOP"),
              ]))
    return [t]


# ── CAPA ──────────────────────────────────────────────────────────────────────

def _capa(d, st):
    inst = d["instalacao"]
    imgs = d.get("imagens", {})
    s = []

    logo = imgs.get("logo", "")
    if logo and os.path.exists(str(logo)):
        s += _embed_img(logo, st, max_w=5*cm, max_h=2.5*cm)
        s.append(_sp(0.5))

    s.append(_sp(1.0))
    inst_nome = inst.get("instituicao", "").replace("\n", "<br/>")
    s.append(Paragraph(inst_nome, st["P_CI"]))
    s.append(_sp(8.0))
    s.append(Paragraph("Plano de Proteção Radiológica", st["P_CT"]))
    s.append(Paragraph(inst.get("nome", ""), st["P_CT"]))
    s.append(_sp(8.0))
    s.append(Paragraph(inst.get("cidade_data", ""), st["P_CC"]))
    s.append(Paragraph(inst.get("ano", ""), st["P_CC"]))
    s.append(PageBreak())
    return s


# ── FOLHA DE ROSTO ────────────────────────────────────────────────────────────

def _rosto(d, st):
    inst = d["instalacao"]
    tl   = d.get("textos_caps", {})
    s = [_sp(1.0)]
    s.append(Paragraph(inst.get("instituicao","").replace("\n","<br/>"), st["P_CI"]))
    s.append(_sp(8.0))
    s.append(Paragraph("Plano de Proteção Radiológica", st["P_CT"]))
    s.append(_sp(1.0))
    resumo = tl.get("resumo_rosto", "")
    if resumo:
        bloco = Table([["", Paragraph(f"<b>{resumo}</b>", st["P_N0"])]],
                      colWidths=[BODY_W*0.4, BODY_W*0.6],
                      style=TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),
                                        ("RIGHTPADDING",(0,0),(-1,-1),0),
                                        ("TOPPADDING",(0,0),(-1,-1),0),
                                        ("BOTTOMPADDING",(0,0),(-1,-1),0),
                                        ("VALIGN",(0,0),(-1,-1),"TOP")]))
        s.append(bloco)
    s.append(_sp(7.0))
    s.append(Paragraph(
        f"{inst.get('cidade_data','')}, {inst.get('mes','')} de {inst.get('ano','')}",
        st["P_CC"]))
    s.append(PageBreak())
    return s


# ── APROVAÇÃO ─────────────────────────────────────────────────────────────────

def _aprovacao(d, st):
    inst = d["instalacao"]
    tl   = d.get("textos_caps", {})
    resp = d.get("responsaveis", [])
    sup  = d.get("supervisor", {})
    sub  = d.get("substituto_supervisor", {})
    s = [_sp(0.5)]
    s.append(Paragraph(inst.get("instituicao","").replace("\n","<br/>"), st["P_CI"]))
    s.append(_sp(1.0))
    intro = tl.get("texto_aprovacao", "")
    if intro: s.append(_p(intro, st))
    s.append(_sp(1.5))
    for r in resp:
        s += _assina(r.get("nome",""), [f"CPF: {r.get('cpf','')}"], st)
    if len(resp) >= 2:
        s.append(_p(f"Em que {resp[1].get('nome','')} representa, por procuração, "
                    "os demais titulares da instalação.", st))
    s.append(_sp(1.0))
    s += _assina(sup.get("nome",""),
                 ["Supervisor de Radioproteção",
                  f"CNEN RT {sup.get('rt','')}"], st)
    s += _assina(sub.get("nome",""),
                 ["Substituto do Supervisor de Radioproteção",
                  f"CNEN RT {sub.get('rt','')}"], st)
    s.append(_sp(2.0))
    s.append(Paragraph(
        f"{inst.get('cidade_data','')}, {inst.get('mes','')} de {inst.get('ano','')}",
        st["P_CC"]))
    s.append(PageBreak())
    return s


# ── LISTA DE TABELAS ──────────────────────────────────────────────────────────

def _lista_tabelas(d, st):
    s = [Paragraph("LISTA DE TABELAS", st["P_PT"])]
    itens = [
        ("B.1","Equipe de Radio-Oncologistas"),
        ("B.2","Equipe de Físicos Médicos"),
        ("B.3","Equipe de Técnicos em Radioterapia"),
        ("B.4","Equipe de Dosimetristas"),
        ("B.5","Equipe de Enfermagem"),
        ("F.1","Fonte de Referência"),
        ("G.1","Conjuntos dosimétricos"),
        ("G.2","Outros instrumentos de medição"),
        ("G.3","Fantomas"),
        ("G.4","Fantoma"),
        ("H.1","Testes diários de segurança"),
        ("H.2","Testes diários dosimétricos"),
        ("H.3","Testes diários mecânicos"),
        ("H.4","Testes mensais de segurança"),
        ("H.5","Testes mensais dosimétricos"),
        ("H.6","Testes mensais mecânicos"),
        ("H.7","Testes anuais de segurança"),
        ("H.8","Testes anuais dosimétricos"),
        ("H.9","Testes anuais mecânicos"),
        ("H.10","Testes diários braquiterapia"),
        ("H.11","Testes trimestrais braquiterapia"),
        ("H.12","Testes mensais ortovoltagem"),
        ("I.1","Monitores de área"),
        ("O.1","Controle de Atestado de Saúde Ocupacional"),
    ]
    for num, titulo in itens:
        s += _toc_row("", f"Tabela {num}–{titulo}", "–", st, sty="P_TS")
    s.append(PageBreak())
    return s


# ── SUMÁRIO ───────────────────────────────────────────────────────────────────

def _sumario(st):
    s = [Paragraph("SUMÁRIO", st["P_PT"])]
    caps = [
        ("1","IDENTIFICAÇÃO DA INSTALAÇÃO"),
        ("2","OBJETIVO DA INSTALAÇÃO E DESCRIÇÃO DAS PRÁTICAS"),
        ("3","ESTRUTURA ORGANIZACIONAL"),
        ("4","DESCRIÇÃO DOS IOES"),
        ("5","CLASSIFICAÇÃO DA INSTALAÇÃO"),
        ("6","CLASSIFICAÇÃO E DESCRIÇÃO DAS ÁREAS"),
        ("7","MECANISMOS E SISTEMAS DE CONTROLE DE ACESSO DE ACESSO ÀS ÁREAS DA INSTALAÇÃO"),
        ("8","DESCRIÇÃO DOS EQUIPAMENTOS E FONTES EMISSORAS DE RADIAÇÃO IONIZANTE"),
        ("9","DESCRIÇÃO DAS FONTES DE REFERÊNCIA"),
        ("10","DESCRIÇÃO DOS INSTRUMENTOS DE DOSIMETRIA"),
        ("11","DESCRIÇÃO DOS MONITORES DE ÁREA"),
        ("12","DESCRIÇÃO DO PROGRAMA DE GARANTIA DA QUALIDADE"),
        ("13","SISTEMAS DE PLANEJAMENTO"),
        ("14","TÉCNICAS DE TRATAMENTO"),
        ("15","CÁLCULO DE BARREIRAS E ESTIMATIVA DE DOSE"),
        ("16","MONITORAÇÃO INDIVIDUAL"),
        ("17","MONITORAÇÃO DE ÁREAS"),
        ("18","GERÊNCIA DE REJEITOS RADIOATIVOS"),
        ("19","DESCRIÇÃO DO CONTROLE MÉDICO DOS IOES - ASO"),
        ("20","PROGRAMA DE TREINAMENTO EM PROTEÇÃO RADIOLÓGICA PARA OS IOES"),
        ("21","PROGRAMA DE EDUCAÇÃO CONTINUADA PARA OS IOES"),
        ("22","NÍVEIS OPERACIONAIS E RESTRIÇÕES"),
        ("23","PROCEDIMENTOS DE EMERGÊNCIA"),
    ]
    for num, titulo in caps:
        s += _toc_row(num, titulo, "–", st, sty="P_TC", upper=True)
    s.append(_sp(0.4))
    s += _toc_row("", "REFERÊNCIAS", "–", st, sty="P_TC", upper=True)
    s.append(_sp(0.4))
    s += _toc_row("", "ANEXOS", "–", st, sty="P_TA")

    anexos = [
        ("A","ESTRUTURA ORGANIZACIONAL",[]),
        ("B","DESCRIÇÃO DOS IOES",[
            ("1","Médicos Radio-Oncologista"),("2","Físicos Médicos"),
            ("3","Técnicos em Radioterapia"),("4","Dosimetrista"),("5","Enfermagem")]),
        ("C","DESCRIÇÃO DAS RESPONSABILIDADES",[
            ("6","Titular da Instalação"),("7","Responsável Técnico e Substituto"),
            ("8","SPR e Substituto"),("9","Especialista em Física da Radioterapia")]),
        ("D","CLASSIFICAÇÃO E DESCRIÇÃO DAS ÁREAS DA INSTALAÇÃO",[
            ("10","Proximidades do 6eX"),
            ("11","Proximidades do TrueBeam, Braquiterapia e Ortovoltagem")]),
        ("E","DESCRIÇÃO DOS EQUIPAMENTOS E FONTES EMISSORAS DE RADIAÇÃO IONIZANTE",[]),
        ("F","DESCRIÇÃO DAS FONTES DE REFERÊNCIA",[]),
        ("G","DESCRIÇÃO DOS INSTRUMENTOS DE DOSIMETRIA",[
            ("12","Câmaras de Ionização e Eletrômetros"),
            ("13","Termômetro(s), Barômetro(s), Nível(is), Régua(s) e Cronômetro(s)"),
            ("14","Fantomas"),("15","Demais Equipamentos"),
            ("16","Descrição dos Controles de Qualidade dos Equipamentos de Dosimetria"),
            ("17","Certificados de Calibração dos Conjuntos Dosimétricos"),
            ("18","Certificados de Calibração dos Demais Itens")]),
        ("H","PROGRAMA DE GARANTIA DA QUALIDADE",[
            ("19","Planilha de Controle de Qualidade e Resultados"),
            ("20","Testes e Tolerâncias"),("20.1","Diários"),("20.2","Mensais"),
            ("20.3","Anuais"),("20.4","Conjuntos Dosimétricos"),
            ("20.5","Braquiterapia"),("20.6","Ortovoltagem"),
            ("21","SEVRRA"),("21.1","Sevrra 6eX"),("21.2","Sevrra GammaMed"),
            ("21.3","Sevrra TrueBeam")]),
        ("I","DESCRIÇÃO DOS MONITORES DE ÁREA",[
            ("22","Certificados de Calibração dos Monitores de Área")]),
        ("J","GERÊNCIA DE REJEITOS RADIOATIVOS",[
            ("23","Descrição e Classificação dos Rejeitos Radioativos"),
            ("24","Procedimentos para Coleta, Segregação, Acondicionamento e Identificação de Rejeitos Radioativos"),
            ("25","Armazenamento em Depósito Inicial"),("26","Tratamento"),
            ("27","Dispensa de Rejeitos"),("28","Registros e Inventários")]),
        ("K","SISTEMAS DE PLANEJAMENTO",[]),
        ("L","TÉCNICAS DE TRATAMENTO",[]),
        ("M","CÁLCULO DE BARREIRAS E ESTIMATIVAS DE DOSE",[
            ("29","Projeto de Blindagem"),("29.1","Cálculo de blindagem 6eX"),
            ("29.2","Cálculo de blindagem TrueBeam"),("29.3","Cálculo de blindagem Braquiterapia"),
            ("30","Levantamento Radiométrico")]),
        ("N","MONITORAÇÃO INDIVIDUAL",[
            ("31","Normas para Utilização dos Dosímetros"),
            ("32","Contrato Monitoração Individual")]),
        ("O","DESCRIÇÃO DO CONTROLE MÉDICO DOS IOES – ASO",[]),
        ("P","PROGRAMA DE TREINAMENTO EM PROTEÇÃO RADIOLÓGICA PARA OS IOES",[]),
        ("Q","PROGRAMA DE EDUCAÇÃO CONTINUADA PARA OS IOES",[]),
        ("R","PROCEDIMENTOS DE EMERGÊNCIA",[]),
    ]
    for letra, titulo, subs in anexos:
        s += _toc_row("", f"ANEXO  {letra} – {titulo}", "–", st, sty="P_TA")
        for num, sub in subs:
            s += _toc_row(num, sub, "–", st, sty="P_TS", indent=1.0*cm)
    s.append(PageBreak())
    return s


# ── CORPO (Seções 1–23) ───────────────────────────────────────────────────────

def _corpo(d, st):
    inst = d["instalacao"]
    tl   = d.get("textos_caps", {})
    s    = []

    def p(txt): s.append(_p(txt, st))
    def p0(txt): s.append(_p(txt, st, ind=False))
    def sp(): s.append(_sp(0.8))
    def blt(txt): s.append(_blt(txt, st))

    s.extend(_cap("1","IDENTIFICAÇÃO DA INSTALAÇÃO",st))
    p(f"O {inst.get('nome','')} (Número de matrícula CNEN {inst.get('matricula_cnen','')}) "
      f"inscrita no C.N.P.J. sob o nº {inst.get('cnpj','')}, encontra-se situado à "
      f"{inst.get('rua','')} {inst.get('complemento','')}– {inst.get('bairro','')}– "
      f"{inst.get('cidade','')}– {inst.get('uf','')}, CEP {inst.get('cep','')}, "
      f"Telefone para contato: {inst.get('telefone','')}.")
    p(f"O Horário de tratamento de pacientes é das {inst.get('horario','')}.")
    sp()

    s.extend(_cap("2","OBJETIVO DA INSTALAÇÃO E DESCRIÇÃO DAS PRÁTICAS",st))
    p(f"A citada instituição tem por objetivo o {inst.get('objetivo','')}.")
    sp()

    s.extend(_cap("3","ESTRUTURA ORGANIZACIONAL",st))
    s.append(_vide("A",st)); sp()

    s.extend(_cap("4","DESCRIÇÃO DOS IOES",st))
    s.append(_vide("B",st)); sp()

    s.extend(_cap("5","CLASSIFICAÇÃO DA INSTALAÇÃO",st))
    p(f"De acordo com a Norma CNEN-NN-6.02, resolução 261/20, de Maio de 2020, "
      f"a instalação é classificada com do GRUPO {inst.get('grupo','')}, "
      f"SUBGRUPO {inst.get('subgrupo','')}.")
    sp()

    s.extend(_cap("6","CLASSIFICAÇÃO E DESCRIÇÃO DAS ÁREAS",st))
    texto = tl.get("classificacao_areas","")
    if texto: p(texto)
    sp()

    s.extend(_cap("7","MECANISMOS E SISTEMAS DE CONTROLE DE ACESSO DE ACESSO ÀS ÁREAS DA INSTALAÇÃO",st))
    texto = tl.get("controle_acesso","")
    if texto: p(texto)
    sp()

    s.extend(_cap("8","DESCRIÇÃO DOS EQUIPAMENTOS E FONTES EMISSORAS DE RADIAÇÃO IONIZANTE",st))
    s.append(_vide("E",st)); sp()
    s.extend(_cap("9","DESCRIÇÃO DAS FONTES DE REFERÊNCIA",st))
    s.append(_vide("F",st)); sp()
    s.extend(_cap("10","DESCRIÇÃO DOS INSTRUMENTOS DE DOSIMETRIA",st))
    s.append(_vide("G",st)); sp()
    s.extend(_cap("11","DESCRIÇÃO DOS MONITORES DE ÁREA",st))
    s.append(_vide("I",st)); sp()

    s.extend(_cap("12","DESCRIÇÃO DO PROGRAMA DE GARANTIA DA QUALIDADE",st))
    txt12 = tl.get("programa_gq","")
    if txt12: p(txt12)
    s.extend(_sec("1","Planilha de Controle e resultados",st))
    txt12p = tl.get("planilha_controle","")
    if txt12p: p(txt12p)
    s.extend(_sec("2","Testes Realizados, Periodicidade e Tolerâncias",st))
    txt12t = tl.get("testes_tolerancias_txt","")
    if txt12t: p(txt12t)
    s.extend(_sec("3","Planejamento de Análise de Riscos",st))
    txt12r = tl.get("analise_riscos","")
    if txt12r: p(txt12r)
    sp()

    s.extend(_cap("13","SISTEMAS DE PLANEJAMENTO",st))
    s.append(_vide("K",st)); sp()
    s.extend(_cap("14","TÉCNICAS DE TRATAMENTO",st))
    s.append(_vide("L",st)); sp()
    s.extend(_cap("15","CÁLCULO DE BARREIRAS E ESTIMATIVA DE DOSE",st))
    s.append(_vide("M",st)); sp()

    s.extend(_cap("16","MONITORAÇÃO INDIVIDUAL",st))
    texto = tl.get("monitoracao_individual","")
    if texto: p(texto)
    sp()

    s.extend(_cap("17","MONITORAÇÃO DE ÁREAS",st))
    texto = tl.get("monitoracao_areas","")
    if texto: p(texto)
    sp()

    s.extend(_cap("18","GERÊNCIA DE REJEITOS RADIOATIVOS",st))
    s.append(_vide("J",st)); sp()

    s.extend(_cap("19","DESCRIÇÃO DO CONTROLE MÉDICO DOS IOES - ASO",st))
    texto = tl.get("controle_medico","")
    if texto: p(texto)
    s.append(_vide("O",st)); sp()

    s.extend(_cap("20","PROGRAMA DE TREINAMENTO EM PROTEÇÃO RADIOLÓGICA PARA OS IOES",st))
    s.append(_vide("P",st)); sp()
    s.extend(_cap("21","PROGRAMA DE EDUCAÇÃO CONTINUADA PARA OS IOES",st))
    s.append(_vide("Q",st)); sp()

    s.extend(_cap("22","NÍVEIS OPERACIONAIS E RESTRIÇÕES",st))
    texto = tl.get("niveis_operacionais","")
    if texto: p(texto)
    sp()

    s.extend(_cap("23","PROCEDIMENTOS DE EMERGÊNCIA",st))
    s.append(_vide("R",st))
    s.append(PageBreak())
    return s


# ── REFERÊNCIAS ───────────────────────────────────────────────────────────────

def _referencias(d, st):
    tl = d.get("textos_caps", {})
    s = [Paragraph("REFERÊNCIAS", st["P_PT"])]
    refs_txt = tl.get("referencias", "")
    for r in [linha.strip() for linha in refs_txt.split("\n") if linha.strip()]:
        s.append(Paragraph(r, st["P_Ref"]))
    s.append(PageBreak())
    return s


# ── DIVISÓRIA ANEXOS ──────────────────────────────────────────────────────────

def _div_anexos(st):
    return [
        Spacer(1, H*0.35),
        Paragraph("ANEXOS", ParagraphStyle("_ax", fontName="Times-Bold",
                   fontSize=20, alignment=TA_CENTER)),
        PageBreak(),
    ]


# ── ANEXO A – Estrutura Organizacional ───────────────────────────────────────

def _anx_a(d, st):
    resp = d.get("responsaveis",[])
    sup  = d.get("supervisor",{})
    sub  = d.get("substituto_supervisor",{})
    rt   = d.get("responsavel_tecnico",{})
    srt  = d.get("substituto_rt",{})
    dir_ = d.get("diretor_clinico",{})
    s = _at("ANEXO  A  –  ESTRUTURA ORGANIZACIONAL", st)

    s.append(Paragraph("<b>Titular da Instalação</b>", st["P_N0"]))
    for r in resp:
        s.append(Paragraph(f"{r.get('nome','')}– CPF {r.get('cpf','')}", st["P_N0"]))
    s.append(_sp(0.4))

    def bloco(titulo, linhas):
        s.append(Paragraph(f"<b>{titulo}</b>", st["P_N0"]))
        for l in linhas: s.append(Paragraph(l, st["P_N0"]))
        s.append(_sp(0.4))

    bloco(f"Identificação do SPR, Responsável Técnico e seus Substitutos",
          [f"SPR: {sup.get('nome','')}", f"RT - {sup.get('rt','')}", f"RA - {sup.get('ra','')}"])
    if rt.get("nome"):
        bloco(f"Responsável Técnico: {rt.get('nome','')}",
              [f"CRM-GO: {rt.get('crm','')}", f"CB - {rt.get('cb','')}"])
    if dir_.get("nome"):
        bloco(f"Diretor Clínico: {dir_.get('nome','')}",
              [f"CRM-GO: {dir_.get('crm','')}"])
    bloco(f"Subst.º. do SPR: {sub.get('nome','')}",
          [f"RT - {sub.get('rt','')}", f"RA – {sub.get('ra','')}"])
    if srt.get("nome"):
        bloco(f"Subst.º. Do Responsável Técnico: {srt.get('nome','')}",
              [f"CRM-GO: {srt.get('crm','')}"])

    s.append(PageBreak())
    return s


# ── ANEXO B – Descrição dos IOEs ─────────────────────────────────────────────

def _anx_b(d, st):
    s = _at("ANEXO  B  –  DESCRIÇÃO DOS IOES", st)

    tl = d.get("textos_caps", {})

    # Médicos
    s.extend(_sec("1","Médicos Radio-Oncologista",st))
    intro = tl.get("intro_medicos","")
    if intro: s.append(_p(intro, st))
    resp_med = tl.get("responsabilidades_medicos","")
    for linha in resp_med.split("\n"):
        linha = linha.strip()
        if linha: s.append(_blt(linha, st))
    med = d.get("equipes_medicos",[])
    if med:
        s.extend(_tabela(["Nome","CRM","RB","Carga Horária"],
                         [[m.get("nome",""),m.get("crm",""),m.get("rb",""),m.get("carga","")] for m in med],
                         [7.5*cm,2.0*cm,2.0*cm,4.0*cm], st, "Tabela B.1 – Equipe de Radio-Oncologistas."))
    s.append(_sp(0.5))

    # Físicos
    s.extend(_sec("2","Físicos Médicos",st))
    fis = d.get("equipes_fisicos",[])
    if fis:
        s.extend(_tabela(["Nome","RT","RA","Formação","Carga"],
                         [[m.get("nome",""),m.get("rt",""),m.get("ra",""),m.get("formacao",""),m.get("carga","")] for m in fis],
                         [5.5*cm,1.5*cm,1.5*cm,4.5*cm,2.5*cm], st, "Tabela B.2 – Equipe de Físicos Médicos."))
    s.append(_sp(0.5))

    # Técnicos
    s.extend(_sec("3","Técnicos em Radioterapia",st))
    tec = d.get("equipes_tecnicos",[])
    if tec:
        s.extend(_tabela(["Nome","CRTR","Carga Horária"],
                         [[m.get("nome",""),m.get("crtr",""),m.get("carga","")] for m in tec],
                         [9.5*cm,2.5*cm,3.5*cm], st, "Tabela B.3 – Equipe de Técnicos em Radioterapia."))
    s.append(_sp(0.5))

    # Dosimetristas
    s.extend(_sec("4","Dosimetrista",st))
    dos = d.get("equipes_dosimetristas",[])
    if dos:
        s.extend(_tabela(["Nome","Registro","Carga Horária"],
                         [[m.get("nome",""),m.get("registro",""),m.get("carga","")] for m in dos],
                         [9.5*cm,2.5*cm,3.5*cm], st, "Tabela B.4 – Equipe de Dosimetristas."))
    s.append(_sp(0.5))

    # Enfermagem
    s.extend(_sec("5","Enfermagem",st))
    enf = d.get("equipes_enfermagem",[])
    if enf:
        s.extend(_tabela(["Nome","COREN","Carga Horária"],
                         [[m.get("nome",""),m.get("coren",""),m.get("carga","")] for m in enf],
                         [8.5*cm,3.0*cm,4.0*cm], st, "Tabela B.5 – Equipe de Enfermagem."))

    dem = d.get("equipes_demais",[])
    if dem:
        s.append(_sp(0.5))
        s.extend(_sec("6","Demais IOEs",st))
        s.extend(_tabela(["Nome","Cargo","Carga"],
                         [[m.get("nome",""),m.get("cargo",""),m.get("carga","")] for m in dem],
                         [7.5*cm,4.0*cm,4.0*cm], st))

    s.append(PageBreak())
    return s


# ── ANEXO C – Responsabilidades ───────────────────────────────────────────────

def _anx_c(d, st):
    tl  = d.get("textos_caps",{})
    sup = d.get("supervisor",{}); sub = d.get("substituto_supervisor",{})
    rt  = d.get("responsavel_tecnico",{}); srt = d.get("substituto_rt",{})
    s = _at("ANEXO  C  –  DESCRIÇÃO DAS RESPONSABILIDADES", st)

    s.extend(_sec("6","Titular da Instalação",st))
    texto = tl.get("resp_titular","")
    if texto: s.append(_p(texto, st))

    s.extend(_sec("7","Responsável Técnico e Substituto",st))
    texto = tl.get("resp_tecnico_texto","")
    if texto: s.append(_p(texto, st))
    if rt.get("nome"):
        s.append(Paragraph(f"<b>Responsável Técnico:</b> {rt.get('nome','')}", st["P_N0"]))
        s.append(Paragraph(f"CRM-GO: {rt.get('crm','')}  CB: {rt.get('cb','')}", st["P_N0"]))
    if srt.get("nome"):
        s.append(Paragraph(f"<b>Substituto:</b> {srt.get('nome','')}", st["P_N0"]))
        s.append(Paragraph(f"CRM-GO: {srt.get('crm','')}  CB: {srt.get('cb','')}", st["P_N0"]))

    s.extend(_sec("8","SPR e Substituto",st))
    if sup.get("nome"):
        s.append(Paragraph(f"<b>SPR:</b> {sup.get('nome','')}", st["P_N0"]))
        s.append(Paragraph(f"RT - {sup.get('rt','')}  RA – {sup.get('ra','')}", st["P_N0"]))
    if sub.get("nome"):
        s.append(Paragraph(f"<b>Subst.º do SPR:</b> {sub.get('nome','')}", st["P_N0"]))
        s.append(Paragraph(f"RT - {sub.get('rt','')}  RA – {sub.get('ra','')}", st["P_N0"]))

    s.extend(_sec("9","Especialista em Física da Radioterapia",st))
    texto = tl.get("resp_fisico","")
    if texto: s.append(_p(texto, st))
    s.append(PageBreak())
    return s


# ── ANEXO D – Classificação de Áreas ─────────────────────────────────────────

def _anx_d(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{}); pdfs_d = d.get("pdfs",{}); imgs_d = d.get("imagens",{})
    s = _at("ANEXO  D  –  CLASSIFICAÇÃO E DESCRIÇÃO DAS ÁREAS DA INSTALAÇÃO", st)
    texto = tl.get("classificacao_areas","")
    if texto: s.append(_p(texto, st))
    for img in imgs_d.get("classificacao_areas",[]):
        s += _embed_img(img, st, legenda=f"Figura D – {os.path.basename(img)}")
    for pf in pdfs_d.get("classificacao_areas",[]): s += rpdf(pf)
    for pf in pdfs_d.get("autorizacao_funcionamento",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


# ── ANEXO E – Equipamentos ────────────────────────────────────────────────────

def _anx_e(d, st):
    equips = d.get("equipamentos",[])
    tl = d.get("textos_caps", {})
    s = _at("ANEXO  E  –  DESCRIÇÃO DOS EQUIPAMENTOS E FONTES EMISSORAS DE RADIAÇÃO IONIZANTE", st)
    txt_e = tl.get("anx_e_intro","")
    if txt_e: s.append(_p(txt_e, st))
    s.append(_sp(0.3))
    for eq in equips:
        campos = [("fabricante","Fabricante"),("modelo","Modelo"),("serie","Nº de Série"),
                  ("fabricacao","Data de Fabricação"),("aceite","Data de Aceite"),
                  ("energia","Energia nominal"),("radiacao","Tipo de Radiação"),
                  ("taxa_dose","Taxa de dose nominal")]
        s.append(Paragraph(f"<b>{eq.get('nome','')}</b>", st["P_N0"]))
        for k, lbl in campos:
            v = eq.get(k,"")
            if v: s.append(Paragraph(f"{lbl}: <b>{v}</b>", st["P_N0"]))
        s.append(_sp(0.4))
    s.append(PageBreak())
    return s


# ── ANEXO F – Fontes de Referência ────────────────────────────────────────────

def _anx_f(d, st):
    fontes = d.get("fontes_referencia",[])
    tl = d.get("textos_caps", {})
    s = _at("ANEXO  F  –  DESCRIÇÃO DAS FONTES DE REFERÊNCIA", st)
    txt_f = tl.get("anx_f_intro","")
    if txt_f: s.append(_p(txt_f, st))
    if fontes:
        s.extend(_tabela(
            ["Fonte Selada","Fabricante","Modelo","Nº Série","Fabricação","Atividade","Tipo"],
            [[f.get("obj",""),f.get("fabricante",""),f.get("modelo",""),f.get("serie",""),
              f.get("fabricacao",""),f.get("atividade",""),f.get("tipo","")] for f in fontes],
            [2.5*cm,2.0*cm,1.8*cm,1.8*cm,2.0*cm,2.0*cm,1.4*cm],
            st, "Tabela F.1 – Fonte de Referência."))
    s.append(PageBreak())
    return s


# ── ANEXO G – Instrumentos de Dosimetria ─────────────────────────────────────

def _anx_g(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{})
    cj = d.get("conjunto_dosimetrico",[]); im = d.get("instrumentos_medicao",[])
    ft = d.get("fantomas",[]); od = d.get("outros_detectores",[]); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  G  –  DESCRIÇÃO DOS INSTRUMENTOS DE DOSIMETRIA", st)
    texto = tl.get("intro_dosimetria","")
    if texto: s.append(_p(texto, st))

    s.extend(_sec("12","Câmaras de Ionização e Eletrômetros",st))
    if cj:
        s.extend(_tabela(["Item","Fabricante","Modelo","Nº Série"],
                         [[f.get("obj",""),f.get("fabricante",""),f.get("modelo",""),f.get("serie","")] for f in cj],
                         [5.0*cm,3.0*cm,3.0*cm,4.5*cm], st, "Tabela G.1 – Conjuntos dosimétricos."))

    s.extend(_sec("13","Termômetro(s), Barômetro(s), Nível(is), Régua(s) e Cronômetro(s)",st))
    if im:
        s.extend(_tabela(["Item","Fabricante","Modelo","Nº Série"],
                         [[f.get("obj",""),f.get("fabricante",""),f.get("modelo",""),f.get("serie","")] for f in im],
                         [5.0*cm,3.0*cm,3.0*cm,4.5*cm], st, "Tabela G.2 – Outros instrumentos de medição."))

    s.extend(_sec("14","Fantomas",st))
    if ft:
        s.extend(_tabela(["Item","Fabricante","Modelo","Dimensões","Material"],
                         [[f.get("obj",""),f.get("fabricante",""),f.get("modelo",""),
                           f.get("dimensoes",""),f.get("material","")] for f in ft],
                         [3.0*cm,2.5*cm,2.0*cm,3.5*cm,4.5*cm], st, "Tabela G.3 – Fantomas."))

    s.extend(_sec("15","Demais Equipamentos",st))
    if od:
        s.extend(_tabela(["Item","Fabricante","Modelo","Nº Série","Data","Tipo"],
                         [[f.get("obj",""),f.get("fabricante",""),f.get("modelo",""),
                           f.get("serie",""),f.get("data",""),f.get("tipo","")] for f in od],
                         [3.0*cm,2.5*cm,2.5*cm,3.0*cm,1.5*cm,2.0*cm], st, "Tabela G.4 – Demais equipamentos."))

    s.extend(_sec("16","Descrição dos Controles de Qualidade dos Equipamentos de Dosimetria",st))
    texto = tl.get("controle_dosimetria","")
    if texto: s.append(_p(texto, st))

    s.extend(_sec("17","Certificados de Calibração dos Conjuntos Dosimétricos",st))
    for pf in pdfs_d.get("certificados_conjunto_dosimetrico",[]): s += rpdf(pf)

    s.extend(_sec("18","Certificados de Calibração dos Demais Itens",st))
    for pf in pdfs_d.get("certificados_outros",[]): s += rpdf(pf)

    s.append(PageBreak())
    return s


# ── ANEXO H – Programa de Garantia da Qualidade ──────────────────────────────

def _anx_h(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{})
    td = d.get("testes_diarios",[]); tm = d.get("testes_mensais",[]); ta = d.get("testes_anuais",[])
    tb = d.get("testes_diarios_braqui",[]); tt = d.get("testes_trimestrais_braqui",[])
    to = d.get("testes_mensais_orto",[]); pdfs_d = d.get("pdfs",{}); imgs_d = d.get("imagens",{})

    s = _at("ANEXO  H  –  PROGRAMA DE GARANTIA DA QUALIDADE", st)

    s.extend(_sec("19","Planilha de Controle de Qualidade e Resultados",st))
    for img in imgs_d.get("programa_qualidade",[]):
        s += _embed_img(img, st, legenda=f"Figura H – {os.path.basename(img)}")

    s.extend(_sec("20","Testes e Tolerâncias",st))
    texto = tl.get("intro_testes","")
    if texto: s.append(_p(texto, st))

    s.extend(_sub("20.1","Diários",st))
    for tipo_n, legenda_n in [("Segurança","H.1 – Testes diários de segurança"),
                               ("Dosimétrico","H.2 – Testes diários dosimétricos"),
                               ("Mecânico","H.3 – Testes diários mecânicos")]:
        f = [t for t in td if t.get("tipo","").lower()==tipo_n.lower()]
        if f: s.extend(_tabela(["Teste","Tolerância"],
                               [[t.get("teste",""),t.get("tolerancia","")] for t in f],
                               [11.0*cm,4.5*cm], st, f"Tabela {legenda_n}."))

    s.extend(_sub("20.2","Mensais",st))
    for tipo_n, legenda_n in [("Segurança","H.4 – Testes mensais de segurança"),
                               ("Dosimétrico","H.5 – Testes mensais dosimétricos"),
                               ("Mecânico","H.6 – Testes mensais mecânicos")]:
        f = [t for t in tm if t.get("tipo","").lower()==tipo_n.lower()]
        if f: s.extend(_tabela(["Teste","Tolerância"],
                               [[t.get("teste",""),t.get("tolerancia","")] for t in f],
                               [11.0*cm,4.5*cm], st, f"Tabela {legenda_n}."))

    s.extend(_sub("20.3","Anuais",st))
    for tipo_n, legenda_n in [("Segurança","H.7 – Testes anuais de segurança"),
                               ("Dosimétrico","H.8 – Testes anuais dosimétricos"),
                               ("Mecânico","H.9 – Testes anuais mecânicos")]:
        f = [t for t in ta if t.get("tipo","").lower()==tipo_n.lower()]
        if f: s.extend(_tabela(["Teste","Tolerância"],
                               [[t.get("teste",""),t.get("tolerancia","")] for t in f],
                               [11.0*cm,4.5*cm], st, f"Tabela {legenda_n}."))

    s.extend(_sub("20.4","Conjuntos Dosimétricos",st))
    texto = tl.get("afericoes_trimestrais","")
    if texto: s.append(_p(texto, st))

    s.extend(_sub("20.5","Braquiterapia",st))
    if tb: s.extend(_tabela(["Teste","Tolerância"],
                             [[t.get("teste",""),t.get("tolerancia","")] for t in tb],
                             [11.0*cm,4.5*cm], st, "Tabela H.10–Testes diários braquiterapia."))
    if tt: s.extend(_tabela(["Teste","Tolerância"],
                             [[t.get("teste",""),t.get("tolerancia","")] for t in tt],
                             [11.0*cm,4.5*cm], st, "Tabela H.11–Testes trimestrais braquiterapia."))

    s.extend(_sub("20.6","Ortovoltagem",st))
    if to: s.extend(_tabela(["Teste","Tolerância"],
                             [[t.get("teste",""),t.get("tolerancia","")] for t in to],
                             [11.0*cm,4.5*cm], st, "Tabela H.12–Testes mensais ortovoltagem."))

    s.extend(_sec("21","SEVRRA",st))
    for pf in pdfs_d.get("sevrra",[]): s += rpdf(pf)
    for pf in pdfs_d.get("auditoria",[]): s += rpdf(pf)

    s.append(PageBreak())
    return s


# ── ANEXO I – Monitores de Área ───────────────────────────────────────────────

def _anx_i(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    mon = d.get("monitores_area",[]); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  I  –  DESCRIÇÃO DOS MONITORES DE ÁREA", st)
    if mon:
        s.extend(_tabela(["Item","Fabricante","Modelo","Nº Série"],
                         [[m.get("obj",""),m.get("fabricante",""),m.get("modelo",""),m.get("serie","")] for m in mon],
                         [4.5*cm,3.5*cm,3.5*cm,4.0*cm], st, "Tabela I.1 – Monitores de área."))
    s.extend(_sec("22","Certificados de Calibração dos Monitores de Área",st))
    for pf in pdfs_d.get("certificados_monitores_area",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


# ── ANEXO J – Gerência de Rejeitos ────────────────────────────────────────────

def _anx_j(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{}); imgs_d = d.get("imagens",{}); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  J  –  GERÊNCIA DE REJEITOS RADIOATIVOS", st)

    s.extend(_sec("23","Descrição e Classificação dos Rejeitos Radioativos",st))
    texto = tl.get("gerencia_rejeitos","")
    if texto: s.append(_p(texto, st))

    for num, titulo in [("24","Procedimentos para Coleta, Segregação, Acondicionamento e Identificação de Rejeitos Radioativos"),
                        ("25","Armazenamento em Depósito Inicial"),
                        ("26","Tratamento"),("27","Dispensa de Rejeitos"),("28","Registros e Inventários")]:
        s.extend(_sec(num, titulo, st))

    for img in imgs_d.get("gerencia_rejeitos",[]):
        s += _embed_img(img, st, legenda=f"Figura J – {os.path.basename(img)}", max_w=BODY_W*0.7)
    for pf in pdfs_d.get("gerencia_rejeitos",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


# ── ANEXO K – Sistemas de Planejamento ───────────────────────────────────────

def _anx_k(d, st):
    sist = d.get("sistemas_planejamento",[])
    s = _at("ANEXO  K  –  SISTEMAS DE PLANEJAMENTO", st)
    for sp in sist:
        s.append(Paragraph(f"<b>{sp.get('nome','')}</b> – {sp.get('fabricante','')}, "
                           f"versão {sp.get('versao','')}", st["P_N0"]))
        if sp.get("tecnicas"):
            s.append(_p(f"Técnicas: {sp.get('tecnicas','')}", st))
    s.append(PageBreak())
    return s


# ── ANEXO L – Técnicas de Tratamento ─────────────────────────────────────────

def _anx_l(d, st):
    tec = d.get("tecnicas_tratamento",[])
    s = _at("ANEXO  L  –  TÉNICAS DE TRATAMEMENTO", st)
    for t in tec:
        s.append(Paragraph(f"<b>{t.get('nome','')}</b>", st["P_N0"]))
        if t.get("descricao"): s.append(_p(t["descricao"], st))
        s.append(_sp(0.3))
    s.append(PageBreak())
    return s


# ── ANEXO M – Cálculo de Barreiras ───────────────────────────────────────────

def _anx_m(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{}); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  M  –  CÁLCULO DE BARREIRAS E ESTIMATIVAS DE DOSE", st)
    texto = tl.get("calculo_barreiras","")
    if texto: s.append(_p(texto, st))
    s.extend(_sec("29","Projeto de Blindagem",st))
    for pf in pdfs_d.get("calculo_blindagem",[]): s += rpdf(pf)
    s.extend(_sec("30","Levantamento Radiométrico",st))
    for pf in pdfs_d.get("levantamento_radiometrico",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


# ── ANEXO N – Monitoração Individual ─────────────────────────────────────────

def _anx_n(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{}); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  N  –  MONITORAÇÃO INDIVIDUAL", st)
    s.extend(_sec("31","Normas para Utilização dos Dosímetros de Controle de Exposição às Radiações Ionizantes",st))
    texto = tl.get("monitoracao_individual","")
    if texto: s.append(_p(texto, st))
    s.extend(_sec("32","Contrato Monitoração Individual",st))
    for pf in pdfs_d.get("contrato_monitoracao",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


# ── ANEXO O – ASOs ────────────────────────────────────────────────────────────

def _anx_o(d, st):
    asos = d.get("asos",[])
    s = _at("ANEXO  O  –  DESCRIÇÃO DO CONTROLE MÉDICO DOS IOES – ASO", st)
    if asos:
        s.extend(_tabela(["IOE","Último ASO","Validade"],
                         [[a.get("nome",""),a.get("ultimo",""),a.get("validade","")] for a in asos],
                         [9.5*cm,3.0*cm,3.0*cm], st,
                         "Tabela O.1 – Controle de Atestado de Saúde Ocupacional."))
    s.append(PageBreak())
    return s


# ── ANEXO P / Q – Treinamento e Educação ──────────────────────────────────────

def _anx_pq(letra, titulo_anx, chave_txt, d, st):
    tl = d.get("textos_caps",{})
    s = _at(f"ANEXO  {letra}  –  {titulo_anx}", st)
    texto = tl.get(chave_txt,"")
    if texto: s.append(_p(texto, st))
    s.append(PageBreak())
    return s


# ── ANEXO R – Procedimentos de Emergência ────────────────────────────────────

def _anx_r(d, st, rpdf=None):
    if rpdf is None: rpdf = lambda p: _embed_pdf_fallback(p, st)
    tl = d.get("textos_caps",{}); pdfs_d = d.get("pdfs",{})
    s = _at("ANEXO  R  –  PROCEDIMENTOS DE EMERGÊNCIA", st)
    texto = tl.get("procedimentos_emergencia","")
    if texto: s.append(_p(texto, st))
    for pf in pdfs_d.get("procedimentos_emergencia",[]): s += rpdf(pf)
    s.append(PageBreak())
    return s


def _embed_pdf_fallback(path, st):
    """Fallback sem tmpdir."""
    if not path or not os.path.exists(str(path)):
        return []
    return [Paragraph(f"[PDF: {os.path.basename(path)}]",
                      ParagraphStyle("_fb", fontName="Times-Roman", fontSize=10,
                                     textColor=CINZA, alignment=TA_CENTER))]


# ── FUNÇÃO PRINCIPAL ──────────────────────────────────────────────────────────

def gerar_pdf(dados: dict, caminho_saida: str) -> None:
    import copy
    dados = copy.deepcopy(dados)
    MESES = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
              "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    hoje = datetime.date.today()
    inst = dados.setdefault("instalacao", {})
    if not inst.get("mes"):  inst["mes"]  = MESES[hoje.month-1]
    if not inst.get("ano"):  inst["ano"]  = str(hoje.year)

    # Diretório temporário para imagens de PDFs embeddados
    # Mantido vivo até o fim do multiBuild
    tmpdir = tempfile.mkdtemp(prefix="ppr_img_")

    def rpdf(path):
        """Embute PDF como páginas de imagem no story."""
        return _embed_pdf(str(path), tmpdir)

    st  = _estilos()
    doc = PPRDoc(caminho_saida, dados, pagesize=A4,
                 title="Plano de Proteção Radiológica",
                 author=inst.get("nome",""),
                 leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB)
    story = []

    story.append(NextPageTemplate("Capa"))
    story.extend(_capa(dados, st))

    story.append(NextPageTemplate("Pre"))
    story.extend(_rosto(dados, st))
    story.extend(_aprovacao(dados, st))
    story.extend(_lista_tabelas(dados, st))
    story.extend(_sumario(st))

    story.append(NextPageTemplate("Corpo"))
    story.extend(_corpo(dados, st))
    story.extend(_referencias(dados, st))
    story.extend(_div_anexos(st))

    story.extend(_anx_a(dados, st))
    story.extend(_anx_b(dados, st))
    story.extend(_anx_c(dados, st))
    story.extend(_anx_d(dados, st, rpdf))
    story.extend(_anx_e(dados, st))
    story.extend(_anx_f(dados, st))
    story.extend(_anx_g(dados, st, rpdf))
    story.extend(_anx_h(dados, st, rpdf))
    story.extend(_anx_i(dados, st, rpdf))
    story.extend(_anx_j(dados, st, rpdf))
    story.extend(_anx_k(dados, st))
    story.extend(_anx_l(dados, st))
    story.extend(_anx_m(dados, st, rpdf))
    story.extend(_anx_n(dados, st, rpdf))
    story.extend(_anx_o(dados, st))
    story.extend(_anx_pq("P","PROGRAMA DE TREINAMENTO EM PROTEÇÃO RADIOLÓGICA PARA OS IOES",
                          "programa_treinamento", dados, st))
    story.extend(_anx_pq("Q","PROGRAMA DE EDUCAÇÃO CONTINUADA PARA OS IOES",
                          "programa_educacao", dados, st))
    story.extend(_anx_r(dados, st, rpdf))

    try:
        doc.multiBuild(story)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
