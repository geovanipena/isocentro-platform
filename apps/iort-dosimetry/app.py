import streamlit as st
import pandas as pd
import os
import re
import math
import tempfile
from datetime import datetime

st.set_page_config(
    page_title="IORT — INTRABEAM EPS",
    page_icon="☢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Main content background ── */
[data-testid="stMain"] { background: #F1F5F9; }
[data-testid="block-container"] { padding: 2rem 2.5rem 3rem; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B1E38 0%, #1E3A5F 55%, #162d4a 100%);
}
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }

/* ── Metric card ── */
.card {
    background: #fff;
    border-radius: 14px;
    padding: 22px 20px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.05), 0 4px 14px rgba(0,0,0,.07);
    margin-bottom: 0;
}
.card-metric { text-align: center; }
.card-metric .value { font-size: 2.4rem; font-weight: 800; line-height: 1.1; }
.card-metric .label {
    font-size: .72rem;
    color: #94A3B8;
    margin-top: 8px;
    text-transform: uppercase;
    letter-spacing: .06em;
    font-weight: 600;
}

/* ── Section header ── */
.sec-header {
    font-size: 1rem;
    font-weight: 700;
    color: #1E3A5F;
    border-left: 3px solid #22C55E;
    padding-left: 10px;
    margin: 28px 0 14px;
    letter-spacing: .01em;
}

/* ── Filter bar ── */
.filter-bar {
    background: #fff;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
    margin-bottom: 20px;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: .78rem;
    font-weight: 600;
}
.badge-green  { background:#DCFCE7; color:#166534; }
.badge-red    { background:#FEE2E2; color:#991B1B; }
.badge-yellow { background:#FEF9C3; color:#854D0E; }
.badge-blue   { background:#DBEAFE; color:#1E40AF; }

/* ── Dataframe container ── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
}

#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def sec(t):
    st.markdown(f'<div class="sec-header">{t}</div>', unsafe_allow_html=True)

def card_metric(label, value, color="#1E3A5F"):
    st.markdown(f"""
    <div class="card card-metric">
        <div class="value" style="color:{color}">{value}</div>
        <div class="label">{label}</div>
    </div>""", unsafe_allow_html=True)

def normalize_quadrant(q):
    if pd.isna(q):
        return "Não informado"
    q = str(q).strip()
    ql = q.lower()
    if any(k in ql for k in ["supero-lateral", "qsl", "qse", "superior lateral", "superiores lateral", "superiores laterais"]):
        return "QSL / QSE"
    if any(k in ql for k in ["supero-medial", "qsm", "qsi", "superior medial", "superiores medial"]):
        return "QSM / QSI"
    if any(k in ql for k in ["infero-lateral", "qil", "qie", "inferior lateral", "inferiores"]):
        return "QIL / QIE"
    if any(k in ql for k in ["infero-medial", "qim", "qii", "inferior medial", "inferior medio"]):
        return "QIM / QII"
    if "retroareolar" in ql:
        return "Retroareolar"
    if any(k in ql for k in ["areolar", "periareolar"]):
        return "Areolar / Periareolar"
    if "central" in ql:
        return "Central"
    if "junção" in ql or "juncao" in ql:
        return "Junção dos quadrantes"
    if "superior" in ql:
        return "Superior (geral)"
    if "inferior" in ql:
        return "Inferior (geral)"
    if "lateral" in ql:
        return "Lateral (geral)"
    return "Outros"

# ── Literatura de referência (INTRABEAM / TARGIT-IORT) ───────────────────────────
# Valores de referência usados para correlacionar os dados do serviço com a
# literatura publicada. Fontes detalhadas na página "Literatura".
LIT = {
    "fonte_kV": 50,                 # fonte pontual de fótons de 50 kV
    "dose_superficie_Gy": 20.0,     # dose prescrita na superfície do aplicador
    "dose_1cm_Gy": (5, 7),          # atenuação a 1 cm de profundidade
    "dose_2cm_Gy": 2,               # ~2 Gy a 2 cm (aplicador de 4 cm)
    "aplicador_min_cm": 1.5,        # menor aplicador esférico disponível
    "aplicador_max_cm": 5.0,        # maior aplicador esférico disponível
    "aplicador_incr_cm": 0.5,       # incremento entre tamanhos
    "aplicadores_comuns": (3.5, 4.0),   # mais usados em séries publicadas
    "conformidade_alvo_pct": 3.0,   # tolerância de desvio de QA (±3%)
    "targit_lr_5a": (3.3, 1.3),     # recidiva local em 5 anos: TARGIT vs EBRT (%)
}

REFERENCIAS = [
    ("Vaidya JS, et al. Targeted intraoperative radiotherapy versus whole breast "
     "radiotherapy for breast cancer (TARGIT-A trial). Lancet 2010;376:91-102.",
     "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(10)60837-9/fulltext"),
    ("Vaidya JS, et al. Risk-adapted targeted intraoperative radiotherapy versus "
     "whole-breast radiotherapy for breast cancer: 5-year results (TARGIT-A). "
     "Lancet 2014;383:603-613.",
     "https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(13)61950-9/fulltext"),
    ("Vaidya JS, et al. Long term survival and local control outcomes from single dose "
     "targeted intraoperative radiotherapy during lumpectomy (TARGIT-IORT) for early "
     "breast cancer. BMJ 2020;370:m2836.",
     "https://www.bmj.com/content/370/bmj.m2836"),
    ("Intraoperative Radiotherapy With INTRABEAM: Technical and Dosimetric "
     "Considerations. Front Oncol 2018;8:74.",
     "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5879442/"),
    ("Schwid M, et al. Therapeutic analysis of Intrabeam-based IORT utilizing a "
     "spherical target volume model. J Appl Clin Med Phys 2017;18(6).",
     "https://aapm.onlinelibrary.wiley.com/doi/10.1002/acm2.12140"),
]

def volume_esferico_cm3(d_cm):
    """Volume-alvo esférico aproximado (modelo de PTV esférico) a partir do
    diâmetro do aplicador, em cm³. Schwid et al., JACMP 2017."""
    if pd.isna(d_cm):
        return float("nan")
    r = d_cm / 2.0
    return (4.0 / 3.0) * math.pi * r ** 3

# ── Data loading ───────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "iort_data.csv")
# Cache em disco do banco já processado. Sobrevive a reinícios do processo no
# Streamlit Cloud (memória/inatividade) que apagam o st.session_state, evitando
# cair de volta na tela de upload e ter de reenviar o .zip/.rar.
CACHE_PATH = os.path.join(tempfile.gettempdir(), "iort_built_cache.csv")


def _write_cache(data):
    """Grava o CSV processado em disco (silencioso em caso de erro de I/O)."""
    try:
        with open(CACHE_PATH, "wb") as f:
            f.write(data)
    except OSError:
        pass


def _clear_cache():
    """Apaga o cache em disco e as chaves de dados da sessão (trocar de base)."""
    try:
        os.remove(CACHE_PATH)
    except OSError:
        pass
    for k in ("iort_built_csv", "iort_archive_bytes"):
        st.session_state.pop(k, None)
    load_data.clear()

import io

# Maps new snake_case export columns → legacy Title Case names used throughout the app
_COL_REMAP = {
    "patient_given_name":               "Patient Given Name",
    "patient_family_name":              "Patient Family Name",
    "patient_id":                       "Patient ID",
    "prescribing_physician":            "Prescribing Physician",
    "responsible_physicist":            "Responsible Physicist",
    "treatment_date":                   "Treatment Date",
    "treatment_number":                 "Treatment #",
    "applicator_size_cm":               "Applicator Size [cm]",
    "applicator_serial_number":         "Applicator Serial Number",
    "dose_delivered_gy":                "Dose Delivered [Gy]",
    "deviation_from_prescription_pct":  "Deviation from Prescription [%]",
    "applicator_sterilizations_to_date":"Applicator Sterilizations to Date",
    "laterality":                       "doc_laterality",
    "quadrant":                         "doc_quadrant",
}

@st.cache_data(max_entries=2)
def load_data(source):
    """source: file path (str) or raw bytes from an uploaded CSV."""
    f = io.BytesIO(source) if isinstance(source, bytes) else source
    df = pd.read_csv(f, low_memory=False)

    # Normalize snake_case columns (new export format → legacy names)
    df = df.rename(columns={k: v for k, v in _COL_REMAP.items() if k in df.columns})
    if "Insurance ID" not in df.columns:
        df["Insurance ID"] = pd.NA

    # Full name
    df["nome"] = (
        df["Patient Given Name"].fillna("") + " " + df["Patient Family Name"].fillna("")
    ).str.strip()

    # Normalize physician names
    df["medico"] = df["Prescribing Physician"].fillna("").str.strip().str.capitalize()
    df["medico"] = df["medico"].replace({"Jean": "Jean Prado", "Nicole": "Dra. Nicole"})

    # Normalize physicist
    df["fisico"] = df["Responsible Physicist"].fillna("").str.strip()
    df["fisico"] = df["fisico"].replace({
        "radiofis": "Radiofis", "Fatima": "Fátima",
    })

    # Parse treatment date — handles both DD-Mon-YY (old) and ISO YYYY-MM-DD (new)
    df["data_proc"] = pd.to_datetime(df["Treatment Date"], format="%d-%b-%y", errors="coerce")
    _nat = df["data_proc"].isna()
    if _nat.any():
        df.loc[_nat, "data_proc"] = pd.to_datetime(
            df.loc[_nat, "Treatment Date"], errors="coerce"
        )
    df["ano"] = df["data_proc"].dt.year.astype("Int64")
    df["mes_ano"] = df["data_proc"].dt.to_period("M").astype(str)

    # Applicator size as float
    df["aplicador_cm"] = pd.to_numeric(df["Applicator Size [cm]"], errors="coerce")

    # Volume-alvo esférico estimado (cm³) — modelo de PTV esférico
    df["volume_cm3"] = df["aplicador_cm"].apply(volume_esferico_cm3)

    # Dose
    df["dose_Gy"] = pd.to_numeric(df["Dose Delivered [Gy]"], errors="coerce")

    # Desvio
    df["desvio_pct"] = pd.to_numeric(df["Deviation from Prescription [%]"], errors="coerce")

    # Sterilizations
    df["esteril"] = pd.to_numeric(df["Applicator Sterilizations to Date"], errors="coerce")

    # Laterality — prefer doc over INTRABEAM field
    df["lateralidade"] = df["doc_laterality"].fillna(df["Insurance ID"])

    # Quadrant normalized
    df["quadrante"] = df["doc_quadrant"].apply(normalize_quadrant)

    # Document status
    df["pdf_ok"] = df["pdf_ok"].map({True: True, "True": True, False: False, "False": False})
    df["doc_ok"] = df["doc_ok"].map({True: True, "True": True, False: False, "False": False})

    return df

def leading_number(name):
    """Número inicial do nome da subpasta (ex.: '90- Kenia ...' -> 90)."""
    m = re.match(r"\s*(\d+)", str(name))
    return int(m.group(1)) if m else None


import unicodedata

_NOME_STOP = {"de", "da", "do", "dos", "das", "e", "di", "del", "la", "ª", "º"}


def _norm_txt(s):
    """Minúsculas sem acentos, para casar nomes de forma robusta."""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _patient_name_from_folder(folder):
    """Nome da paciente a partir do nome da subpasta: tira o número inicial
    ('5- ', '10 - ', '101. ') e a data no fim ('29-01-19')."""
    s = re.sub(r"^\s*\d+\s*[-.\)ºª]*\s*", "", str(folder))
    s = re.sub(r"\s*\d{1,2}[-_/.]\d{1,2}[-_/.]\d{2,4}\s*$", "", s)
    return s.strip()


def _name_tokens(name):
    """Tokens significativos do nome (>=3 letras, sem conectivos)."""
    out = []
    for tok in re.split(r"\s+", _norm_txt(name)):
        tok = re.sub(r"[^a-z]", "", tok)
        if len(tok) >= 3 and tok not in _NOME_STOP:
            out.append(tok)
    return out


def _name_status(text, tokens):
    """Status do nome da paciente num documento:
    True  = nome encontrado (>=2 tokens, ou o único token);
    False = texto legível mas sem o nome;
    None  = não dá para verificar (ilegível/scan, ou sem nome para conferir)."""
    if not text:
        return None
    norm = _norm_txt(text)
    if sum(c.isalpha() for c in norm) < 15:      # quase sem texto = scan/ilegível
        return None
    if not tokens:                               # sem nome derivável da pasta
        return None
    found = sum(1 for t in tokens if re.search(r"\b" + re.escape(t) + r"\b", norm))
    return found >= min(2, len(tokens))


def _file_motivo(present, statuses):
    """Status do arquivo para revisão pasta a pasta:
    'ausente' | 'nome não confere' | 'presente (ilegível, assumido ok)' | 'ok'."""
    if not present:
        return "ausente"
    if any(s is True for s in statuses):
        return "ok"
    if any(s is None for s in statuses):         # presente mas ilegível → não penaliza
        return "presente (ilegível, assumido ok)"
    return "nome não confere"                     # legível em todos e sem o nome


_MOTIVO_PEND = {"ausente", "nome não confere"}    # motivos que tornam a pasta pendência


def _detect_laterality(texts, insurance_id=""):
    """Lateralidade (Direita/Esquerda) a partir de várias fontes, em ordem de
    confiança: 'Application Type: Right/Left Breast' do PDF INTRABEAM → campo
    'Insurance ID' (Mama Dir./Esq.) → texto do PDF/laudo ('mama direita/esquerda')."""
    blob = _norm_txt(" \n ".join(t for t in texts if t))
    if re.search(r"\bright breast\b", blob):
        return "Direita"
    if re.search(r"\bleft breast\b", blob):
        return "Esquerda"
    ins = _norm_txt(insurance_id)
    if "dir" in ins:
        return "Direita"
    if "esq" in ins:
        return "Esquerda"
    if re.search(r"mama\s+direita|mama\s+dir\b|\bdireita\b|\bdireito\b", blob):
        return "Direita"
    if re.search(r"mama\s+esquerda|mama\s+esq\b|\besquerda\b|\besquerdo\b", blob):
        return "Esquerda"
    return ""


def _fmt_pid(v):
    """Patient ID legível: '41565' em vez de '41565.0'; vazio para NaN."""
    if pd.isna(v):
        return ""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(v)
    except (TypeError, ValueError):
        return str(v)


def _docx_text(data):
    """Texto de um .docx (lê word/document.xml). Devolve None se não for um .docx
    legível (ex.: .doc binário antigo, UTF-16) — aí o nome não é verificável."""
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        return re.sub(r"<[^>]+>", " ", xml)
    except Exception:
        return None


def _open_archive_entries(arc_bytes):
    """Abre um .zip ou .rar e devolve (names, read_fn, size_of, cleanup).

    ZIP é lido na memória (zipfile). RAR é extraído para uma pasta temporária com
    `unar` e lido do disco — `unar` não faz streaming de um arquivo para stdout,
    então a leitura por entrada do rarfile falha ('got=0'); extrair resolve isso."""
    import zipfile

    sig = arc_bytes[:4]
    if sig in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        z = zipfile.ZipFile(io.BytesIO(arc_bytes))
        infos = [i for i in z.infolist() if not i.is_dir()]
        size_of = {i.filename: i.file_size for i in infos}
        return list(size_of), z.read, size_of, (lambda: None)

    if sig == b"Rar!":
        import tempfile
        import shutil
        import subprocess

        d = tempfile.mkdtemp(prefix="iort_rar_")
        src = os.path.join(d, "_in.rar")
        out = os.path.join(d, "ex")
        with open(src, "wb") as fh:
            fh.write(arc_bytes)
        try:
            # check=False: o unar segue extraindo as demais entradas mesmo que uma
            # ou outra (ex.: .docx corrompido) falhe — aqui só os PDFs importam.
            proc = subprocess.run(
                ["unar", "-quiet", "-force-overwrite", "-output-directory", out, src],
                capture_output=True,
            )
        except FileNotFoundError:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError("Ferramenta 'unar' não encontrada para abrir .rar.")

        size_of = {}
        for root, _, fnames in os.walk(out):
            for fn in fnames:
                ap = os.path.join(root, fn)
                size_of[os.path.relpath(ap, out)] = os.path.getsize(ap)
        if not size_of:
            err = (proc.stderr or proc.stdout or b"").decode("utf-8", "ignore")[:200]
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError(f"Não foi possível extrair o .rar: {err}")
        read_fn = lambda rel: open(os.path.join(out, rel), "rb").read()
        return list(size_of), read_fn, size_of, (lambda: shutil.rmtree(d, ignore_errors=True))

    raise ValueError("Envie um arquivo .zip ou .rar válido da pasta de relatórios.")


def _build_csv(arc_bytes, junction_tol=0.5, progress=None):
    """Lê um .zip ou .rar da pasta-mãe (subpastas de relatórios INTRABEAM) e devolve
    um CSV (bytes) no formato do iort_data. Para cada subpasta: localiza o relatório
    de tratamento (PDF), extrai os campos da página 1, classifica o quadrante e marca
    pdf_ok/doc_ok conforme os arquivos presentes (subpasta sem PDF/DOC = pendência).
    `progress(i, n, nome)` é chamado por subpasta para alimentar a barra de progresso."""
    import iort_quadrant as iq

    names, read_fn, size_of, cleanup = _open_archive_entries(arc_bytes)
    try:
        return _build_rows(names, read_fn, size_of, iq, junction_tol, progress)
    finally:
        cleanup()


def _build_rows(names, read_fn, size_of, iq, junction_tol, progress=None):
    if not names:
        raise ValueError("Arquivo vazio.")

    # Agrupa por subpasta de PACIENTE = filho direto da pasta-mãe do arquivo
    # (ex.: 'INTRABEAM NOVO/10 - Maura/...'  → paciente = '10 - Maura'). Conta um
    # grupo por subpasta, ignorando o que houver dentro dela (datas, imagens, etc.).
    comps_by_name = {n: [c for c in re.split(r"[\\/]", n) if c] for n in size_of}
    # Profundidade da pasta-mãe: 1 se há uma única pasta no topo embrulhando tudo
    # (caso comum: 'INTRABEAM NOVO/'); 0 se as subpastas já estão na raiz do arquivo.
    tops = {c[0] for c in comps_by_name.values() if len(c) >= 2}
    depth = 1 if len(tops) == 1 else 0
    groups = {}
    for n, comps in comps_by_name.items():
        if len(comps) <= depth + 1:
            continue                          # arquivo solto na raiz — não é paciente
        folder = comps[depth]                 # subpasta logo abaixo da pasta-mãe
        if re.match(r"\s*\d+", folder):       # convenção: paciente é pasta numerada
            groups.setdefault(folder, []).append(n)
    if not groups:
        raise ValueError("Nenhuma subpasta de paciente encontrada "
                         "(esperado: pasta-mãe com subpastas numeradas).")

    def _score(e):
        b = os.path.basename(e).lower()
        sz = size_of.get(e, 1e12)
        s = 0
        if "intrabeam" in b:
            s -= 4
        if re.search(r"(^|[ _-])rt([ _-]|$)", b):
            s -= 2
        if sz < 500_000:           # o relatório de tratamento é pequeno (~100 KB)
            s -= 1
        return (s, sz)

    rows = []
    ordered = sorted(groups.items(), key=lambda kv: leading_number(kv[0]) or 1e9)
    total = len(ordered)
    for idx, (folder, entries) in enumerate(ordered, 1):
        if progress is not None:
            progress(idx, total, folder)
        nofake = lambda e: not os.path.basename(e).startswith("~$")
        pdfs = [e for e in entries if e.lower().endswith(".pdf") and nofake(e)]
        docs = [e for e in entries if e.lower().endswith((".doc", ".docx")) and nofake(e)]
        tokens = _name_tokens(_patient_name_from_folder(folder))

        # ── PDF: status do nome por arquivo + relatório INTRABEAM para os dados ──
        pdf_status, pdf_texts, fields, code, obs, used = [], [], {}, "", "", ""
        for e in sorted(pdfs, key=_score):
            try:
                data = read_fn(e)
                text = iq.read_text(data)
            except Exception:
                pdf_status.append(None)        # PDF vazio/corrompido — ilegível
                continue
            pdf_texts.append(text)
            pdf_status.append(_name_status(text, tokens))
            f = iq.parse_fields(text)
            if f.get("Patient ID") and not fields:   # relatório de tratamento INTRABEAM
                fields, used = f, os.path.basename(e)
                try:
                    r = iq.classify_pdf(data, laterality=iq.parse_laterality(text),
                                        junction_tol=junction_tol)
                    code = r["code"]
                    obs = f"{r['description']}; mama={r['laterality']}; pdf={used}"
                except Exception as ex:
                    obs = f"erro: {ex}; pdf={used}"

        # ── DOC: status do nome por arquivo ──
        doc_status, doc_texts = [], []
        for e in docs:
            try:
                dt = _docx_text(read_fn(e))
            except Exception:
                dt = None
            doc_texts.append(dt)
            doc_status.append(_name_status(dt, tokens))

        # Pendência só se faltar o arquivo ou o nome claramente não conferir (legível).
        pdf_motivo = _file_motivo(bool(pdfs), pdf_status)
        doc_motivo = _file_motivo(bool(docs), doc_status)
        pdf_ok = pdf_motivo not in _MOTIVO_PEND
        doc_ok = doc_motivo not in _MOTIVO_PEND

        # Lateralidade: Application Type do PDF → Insurance ID → texto do PDF/laudo.
        lat = _detect_laterality(pdf_texts + doc_texts, fields.get("Insurance ID", ""))
        # Nome para a tabela: do relatório INTRABEAM; senão, do nome da pasta.
        nome_pasta = _patient_name_from_folder(folder)
        if not obs:
            obs = f"PDF: {pdf_motivo}; DOC: {doc_motivo}"
        rows.append({
            "folder_number": leading_number(folder) or "",
            "folder_name": folder,
            "patient_given_name": fields.get("Patient Given Name") or nome_pasta,
            "patient_family_name": fields.get("Patient Family Name", ""),
            "patient_id": fields.get("Patient ID", ""),
            "treatment_number": fields.get("Treatment #", ""),
            "treatment_date": fields.get("Treatment Date", ""),
            "prescribing_physician": fields.get("Prescribing Physician", ""),
            "responsible_physicist": fields.get("Responsible Physicist", ""),
            "applicator_size_cm": fields.get("Applicator Size [cm]", ""),
            "applicator_serial_number": fields.get("Applicator Serial Number", ""),
            "applicator_sterilizations_to_date": fields.get("Applicator Sterilizations to Date", ""),
            "dose_delivered_gy": fields.get("Dose Delivered [Gy]", ""),
            "deviation_from_prescription_pct": fields.get("Deviation from Prescription [%]", ""),
            "laterality": lat,
            "quadrant": fields.get("Other ID", ""),
            "pdf_ok": pdf_ok,
            "doc_ok": doc_ok,
            "pdf_motivo": pdf_motivo,
            "doc_motivo": doc_motivo,
            "quadrant_auto": code,
            "quadrant_auto_obs": obs,
        })

    rows = _dedup_patients(rows)
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def _identity(r):
    """Identidade da paciente para deduplicar: Patient ID do relatório INTRABEAM;
    na falta dele, o nome normalizado (ou o nome da pasta)."""
    pid = str(r.get("patient_id") or "").strip()
    if pid:
        return "id:" + pid
    nm = _norm_txt((str(r.get("patient_given_name") or "") + " " +
                    str(r.get("patient_family_name") or "")).strip())
    return "nm:" + nm if nm else "pasta:" + _norm_txt(r.get("folder_name") or "")


def _dedup_patients(rows):
    """1 tratamento = 1 paciente (PDF+DOC). Funde duplicados/subpastas do mesmo
    paciente: mantém o registro mais completo e combina pdf_ok/doc_ok."""
    def _score(r):
        return (bool(str(r.get("patient_id") or "").strip()),    # tem dados INTRABEAM
                bool(r.get("pdf_ok") and r.get("doc_ok")),        # par completo
                bool(r.get("quadrant_auto")))                     # quadrante classificado

    out = {}
    for r in rows:
        k = _identity(r)
        cur = out.get(k)
        if cur is None:
            out[k] = dict(r)
        else:
            keep = dict(cur if _score(cur) >= _score(r) else r)
            keep["pdf_ok"] = bool(cur.get("pdf_ok") or r.get("pdf_ok"))
            keep["doc_ok"] = bool(cur.get("doc_ok") or r.get("doc_ok"))
            out[k] = keep
    return list(out.values())


def pendencias_df(df):
    """Registros cujo relatório está incompleto — sem PDF e/ou sem DOC na pasta.
    Derivado das colunas pdf_ok/doc_ok do próprio iort_data (resultado da leitura
    das pastas de relatórios)."""
    falta_pdf = ~df["pdf_ok"].eq(True) if "pdf_ok" in df.columns else pd.Series(False, index=df.index)
    falta_doc = ~df["doc_ok"].eq(True) if "doc_ok" in df.columns else pd.Series(False, index=df.index)
    return df[falta_pdf | falta_doc].copy()

# ── Resolve data source (disk → session state → upload screen) ─────────────────
_upload_error = None
_data_loaded = False

if os.path.exists(DATA_PATH):
    df = load_data(DATA_PATH)
    _data_loaded = True
elif "iort_built_csv" in st.session_state:
    # Já montado: carrega do CSV em cache; os bytes do arquivo já foram liberados.
    try:
        df = load_data(st.session_state["iort_built_csv"])
        _data_loaded = True
    except Exception as _e:
        _upload_error = str(_e)
        st.session_state.pop("iort_built_csv", None)
elif os.path.exists(CACHE_PATH):
    # O processo reiniciou (apagando o session_state), mas o banco já processado
    # ainda está em disco: recarrega na hora, sem reenviar o arquivo.
    try:
        with open(CACHE_PATH, "rb") as _f:
            _cached = _f.read()
        df = load_data(_cached)
        st.session_state["iort_built_csv"] = _cached   # reativa o botão "Salvar banco"
        _data_loaded = True
    except Exception:
        try:
            os.remove(CACHE_PATH)
        except OSError:
            pass
elif "iort_archive_bytes" in st.session_state:
    try:
        _bar = st.progress(0.0, text="Preparando os relatórios…")

        def _cb(i, n, name):
            _bar.progress(i / n, text=f"Processando subpasta {i}/{n}: {name[:45]}")

        _csv_bytes = _build_csv(st.session_state["iort_archive_bytes"], progress=_cb)
        st.session_state["iort_built_csv"] = _csv_bytes
        _write_cache(_csv_bytes)                  # persiste p/ sobreviver a reinícios
        _bar.empty()
        # Libera ~dezenas de MB: os bytes do .zip/.rar não são mais necessários.
        del st.session_state["iort_archive_bytes"]
        import gc
        gc.collect()
        st.rerun()
    except Exception as _e:
        _upload_error = str(_e)
        st.session_state.pop("iort_archive_bytes", None)
        st.session_state.pop("iort_built_csv", None)

if not _data_loaded:
    with st.sidebar:
        st.markdown("## ☢️ IORT — INTRABEAM")
        st.markdown("**Instituto de Mastologia de Goiânia**")

    st.markdown("""
    <div style="max-width:520px;margin:80px auto 0;text-align:center;">
      <div style="font-size:3rem;margin-bottom:16px;">☢️</div>
      <div style="font-size:1.5rem;font-weight:700;color:#1E3A5F;margin-bottom:8px;">
        IORT — INTRABEAM
      </div>
      <div style="color:#64748B;margin-bottom:32px;">
        Carregue os arquivos de dados para continuar.
      </div>
    </div>
    """, unsafe_allow_html=True)

    if _upload_error:
        st.error(f"Arquivo inválido — {_upload_error}. Verifique se enviou o arquivo correto.")

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown(
            '<div class="card" style="color:#1E293B;line-height:1.55;">'
            'Envie um <b>.zip ou .rar da pasta-mãe</b> (ex.: <code>INTRABEAM NOVO</code>) '
            'contendo as <b>subpastas</b> das pacientes com os relatórios do INTRABEAM '
            'em PDF.<br><br>O app lê cada subpasta, monta os dados, classifica o quadrante '
            'e aponta as subpastas sem PDF/DOC em <b>Pendências</b>.<br><br>'
            '💡 <b>Dica:</b> após processar, use <b>“Salvar banco (CSV)”</b> na barra lateral. '
            'Na próxima vez, envie esse <b>.csv</b> abaixo para carregar na hora, sem reprocessar.'
            '</div>',
            unsafe_allow_html=True,
        )
        up_arc = st.file_uploader(
            "1ª vez — pasta de relatórios INTRABEAM (.zip ou .rar)",
            type=["zip", "rar"],
            key="up_arc",
        )
        up_csv = st.file_uploader(
            "OU banco já processado (.csv) — carrega rápido",
            type="csv",
            key="up_csv",
        )
        if st.button("Carregar dados", type="primary",
                     disabled=(up_arc is None and up_csv is None)):
            _clear_cache()                               # descarta base anterior em disco
            if up_csv is not None:                       # CSV salvo → carrega direto
                _data = up_csv.read()
                st.session_state["iort_built_csv"] = _data
                _write_cache(_data)
                st.session_state.pop("iort_archive_bytes", None)
            else:                                        # arquivo bruto → processa
                st.session_state["iort_archive_bytes"] = up_arc.read()
                st.session_state.pop("iort_built_csv", None)
            st.rerun()

    st.stop()

# ── Pendências derivadas da própria base (pastas com arquivo faltando) ─────────
df_miss = pendencias_df(df)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ☢️ IORT — INTRABEAM")
    st.markdown("**Instituto de Mastologia de Goiânia**")
    st.divider()
    pagina = st.radio(
        "nav",
        ["Análise", "Tratamentos", "Literatura", "Pendências"],
        label_visibility="collapsed",
    )
    st.divider()

    # Quick filters (persisted via session_state)
    st.markdown("**Filtros rápidos**")
    anos_disp = sorted([a for a in df["ano"].dropna().unique()], reverse=True)
    ano_sel = st.multiselect("Ano", anos_disp, default=anos_disp, key="f_ano")
    medico_sel = st.multiselect(
        "Médico", sorted(df["medico"].unique()), default=sorted(df["medico"].unique()), key="f_med"
    )
    fisico_sel = st.multiselect(
        "Físico", sorted(df["fisico"].unique()), default=sorted(df["fisico"].unique()), key="f_fis"
    )

    st.divider()
    _completo = (df["pdf_ok"].eq(True) & df["doc_ok"].eq(True)).sum()
    _com_doc = df["doc_ok"].eq(True).sum()
    _pend = len(pendencias_df(df))
    st.caption(f"Pacientes (sem duplicar): **{len(df)}**")
    st.caption(f"Tratamentos (PDF+DOC): **{_completo}**  ·  com DOC: **{_com_doc}**")
    st.caption(f"Pendências: **{_pend}**")
    if "quadrant_auto" in df.columns:
        n_auto = df["quadrant_auto"].fillna("").astype(str).str.strip().ne("").sum()
        st.caption(f"Quadrante (auto) via PDF: **{n_auto}** classificado(s)")
    st.caption(f"Atualizado: {datetime.today().strftime('%d/%m/%Y')}")

    _built = st.session_state.get("iort_built_csv")
    if _built:
        st.download_button(
            "💾 Salvar banco (CSV)", data=_built,
            file_name="iort_data_processado.csv", mime="text/csv",
            help="Guarde este CSV. Na próxima vez, envie-o na tela inicial para "
                 "carregar instantaneamente, sem reprocessar o .zip/.rar.",
        )
        if st.button("🔄 Carregar outro arquivo",
                     help="Descarta a base atual e volta à tela de upload."):
            _clear_cache()
            st.rerun()

# ── Apply global filters ───────────────────────────────────────────────────────
mask = pd.Series(True, index=df.index)
if ano_sel:
    mask &= df["ano"].isin(ano_sel)
if medico_sel:
    mask &= df["medico"].isin(medico_sel)
if fisico_sel:
    mask &= df["fisico"].isin(fisico_sel)
dff = df[mask].copy()

# ── Pages ──────────────────────────────────────────────────────────────────────

def page_dashboard():
    sec("Visão Geral — INTRABEAM")

    n = len(dff)
    n_pdf = dff["pdf_ok"].eq(True).sum()
    n_doc = dff["doc_ok"].eq(True).sum()
    n_pend = len(df_miss)
    dose_med = dff["dose_Gy"].mean()

    c1, c2, c3, c4, c5 = st.columns(5, gap="medium")
    with c1:
        card_metric("Tratamentos", n, "#1E3A5F")
    with c2:
        card_metric("Com PDF", n_pdf, "#22C55E")
    with c3:
        card_metric("Com DOC", n_doc, "#22C55E")
    with c4:
        card_metric("Pendências", n_pend, "#EF4444" if n_pend else "#64748B")
    with c5:
        card_metric("Dose média (Gy)", f"{dose_med:.2f}" if not pd.isna(dose_med) else "—", "#F59E0B")

    col_a, col_b = st.columns(2, gap="medium")

    with col_a:
        sec("Tratamentos por Ano")
        por_ano = dff.groupby("ano").size().reset_index(name="n")
        por_ano["ano"] = por_ano["ano"].astype(str)
        st.bar_chart(por_ano.set_index("ano")["n"], use_container_width=True)

    with col_b:
        sec("Tamanho do Aplicador (cm)")
        apl = dff["aplicador_cm"].value_counts().sort_index()
        st.bar_chart(apl, use_container_width=True)

    col_c, col_d = st.columns(2, gap="medium")

    with col_c:
        sec("Lateralidade")
        lat = (dff["lateralidade"].fillna("Não informado").replace("", "Não informado")
               .value_counts())
        st.bar_chart(lat, use_container_width=True)
        st.caption(f"Direita + Esquerda + Não informado = {int(lat.sum())} (total de tratamentos). "
                   "'Não informado' = sem relatório INTRABEAM digital com o campo de lateralidade.")

    with col_d:
        sec("Quadrante (documentado)")
        quad = dff["quadrante"].value_counts()
        st.bar_chart(quad, use_container_width=True)

    col_e, col_f = st.columns(2, gap="medium")

    with col_e:
        sec("Quadrante — Detecção por Imagem")
        if "quadrant_auto" in dff.columns:
            qa = (dff["quadrant_auto"].fillna("").astype(str).str.strip())
            qa = qa[qa.ne("")].value_counts()
            if qa.empty:
                st.info("Nenhum quadrante classificado por imagem ainda.")
            else:
                st.bar_chart(qa, use_container_width=True)
                st.caption(f"{int(qa.sum())} de {len(dff)} tratamento(s) com quadrante detectado "
                           "no diagrama do INTRABEAM (QSL/QSM/QIL/QIM/Areolar/Junção).")
        else:
            st.info("Sem dados de quadrante por imagem.")

    with col_f:
        sec("Lateralidade × Quadrante (documentado)")
        lat_c = dff["lateralidade"].fillna("Não informado").replace("", "Não informado")
        quad_c = dff["quadrante"].fillna("Não informado").replace("", "Não informado")
        cross_lq = pd.crosstab(quad_c, lat_c)
        if cross_lq.empty:
            st.info("Sem dados suficientes para correlacionar.")
        else:
            st.bar_chart(cross_lq, use_container_width=True)
            st.caption("Quadrante documentado por lateralidade — barras agrupadas por mama "
                       "(Direita/Esquerda).")

    sec("Lateralidade × Quadrante (detecção por imagem)")
    if "quadrant_auto" in dff.columns:
        qa_c = dff["quadrant_auto"].fillna("").astype(str).str.strip()
        mask_auto = qa_c.ne("")
        if mask_auto.any():
            lat_auto = (dff.loc[mask_auto, "lateralidade"].fillna("Não informado")
                        .replace("", "Não informado"))
            cross_qa = pd.crosstab(qa_c[mask_auto], lat_auto)
            st.bar_chart(cross_qa, use_container_width=True)
            st.caption(f"{int(mask_auto.sum())} tratamento(s) com quadrante detectado no diagrama, "
                       "distribuídos por mama (Direita/Esquerda).")
        else:
            st.info("Nenhum quadrante classificado por imagem ainda.")
    else:
        st.info("Sem dados de quadrante por imagem.")

    sec("Últimos 10 Tratamentos")
    _num_col = "Treatment #" if "Treatment #" in dff.columns else dff.columns[0]
    cols_show = [_num_col, "nome", "data_proc", "aplicador_cm", "dose_Gy",
                 "lateralidade", "quadrante", "medico", "fisico"]
    cols_show = [c for c in cols_show if c in dff.columns]
    ultimos = dff.sort_values("data_proc", ascending=False).head(10)[cols_show].copy()
    ultimos["data_proc"] = ultimos["data_proc"].dt.strftime("%d/%m/%Y")
    col_labels = {"Treatment #": "Nº", "nome": "Paciente", "data_proc": "Data",
                  "aplicador_cm": "Aplicador (cm)", "dose_Gy": "Dose (Gy)",
                  "lateralidade": "Lateralidade", "quadrante": "Quadrante",
                  "medico": "Médico", "fisico": "Físico"}
    ultimos.columns = [col_labels.get(c, c) for c in cols_show]
    st.dataframe(ultimos, use_container_width=True, hide_index=True)


def page_tratamentos():
    sec("Registros de Tratamento")

    col_busca, col_lat, col_apl = st.columns([3, 1, 2])
    with col_busca:
        busca = st.text_input("🔍 Buscar por nome ou nº", placeholder="Digite para filtrar...")
    with col_lat:
        lat_f = st.selectbox("Lateralidade", ["Todas", "Direita", "Esquerda"], key="lat_f")
    with col_apl:
        apl_f = st.multiselect(
            "Aplicador (cm)", sorted(dff["aplicador_cm"].dropna().unique()),
            default=sorted(dff["aplicador_cm"].dropna().unique()), key="apl_f"
        )

    resultado = dff.copy()
    if busca:
        mask_b = resultado.apply(lambda r: busca.lower() in str(r).lower(), axis=1)
        resultado = resultado[mask_b]
    if lat_f != "Todas":
        resultado = resultado[resultado["lateralidade"].str.contains(lat_f, na=False)]
    if apl_f:
        resultado = resultado[resultado["aplicador_cm"].isin(apl_f)]

    _col_map = {
        "Treatment #": "Nº", "nome": "Paciente", "Patient ID": "ID", "data_proc": "Data",
        "aplicador_cm": "Aplicador (cm)", "dose_Gy": "Dose (Gy)",
        "desvio_pct": "Desvio (%)", "esteril": "Esterilizações",
        "lateralidade": "Lateralidade", "quadrante": "Quadrante",
        "quadrant_auto": "Quadrante (auto)",
        "medico": "Médico", "fisico": "Físico", "pdf_ok": "PDF ✓", "doc_ok": "DOC ✓",
    }
    cols_show = [c for c in _col_map if c in resultado.columns]
    exib = resultado[cols_show].copy()
    exib["data_proc"] = exib["data_proc"].dt.strftime("%d/%m/%Y")
    exib.columns = [_col_map[c] for c in cols_show]
    st.dataframe(exib, use_container_width=True, hide_index=True)
    st.caption(f"{len(exib)} registro(s) encontrado(s)")

    csv = resultado.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar seleção (CSV)", data=csv,
                       file_name="iort_selecao.csv", mime="text/csv")


def page_analise():
    sec("Análise Estatística — INTRABEAM")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Aplicadores", "Dose & Conformidade", "Volume-Alvo", "Tendência Temporal", "Esterilizações"]
    )

    # ── Aplicadores ──────────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            sec("Distribuição por Aplicador")
            apl = dff["aplicador_cm"].value_counts().sort_index()
            apl.index = apl.index.astype(str) + " cm"
            st.bar_chart(apl)

        with c2:
            sec("Aplicador × Lateralidade")
            cross = pd.crosstab(dff["aplicador_cm"].astype(str) + " cm", dff["lateralidade"])
            st.dataframe(cross, use_container_width=True)

        sec("Aplicador × Quadrante")
        cross2 = pd.crosstab(dff["quadrante"], dff["aplicador_cm"].astype(str) + " cm")
        st.dataframe(cross2, use_container_width=True)

        # Correlação com a literatura: faixa disponível e tamanhos mais comuns
        apl_validos = dff["aplicador_cm"].dropna()
        if not apl_validos.empty:
            mediana = apl_validos.median()
            comuns = set(LIT["aplicadores_comuns"])
            pct_comuns = apl_validos.isin(comuns).mean() * 100
            fora_faixa = ((apl_validos < LIT["aplicador_min_cm"]) |
                          (apl_validos > LIT["aplicador_max_cm"])).sum()
            st.info(
                f"📚 **Correlação com a literatura** — aplicadores esféricos INTRABEAM vão de "
                f"**{LIT['aplicador_min_cm']:.1f} a {LIT['aplicador_max_cm']:.1f} cm** (incrementos de "
                f"{LIT['aplicador_incr_cm']:.1f} cm). Em séries publicadas os de **3,5 e 4,0 cm** são os "
                f"mais usados. Neste serviço: mediana **{mediana:.1f} cm**, "
                f"**{pct_comuns:.0f}%** dos casos com 3,5/4,0 cm"
                + (f"; ⚠️ **{fora_faixa}** registro(s) fora da faixa 1,5–5,0 cm." if fora_faixa else ".")
            )

    # ── Dose & Conformidade ──────────────────────────────────────────────────
    with tab2:
        c3, c4, c5 = st.columns(3)
        c3.metric("Dose média (Gy)", f"{dff['dose_Gy'].mean():.3f}",
                  help="Referência TARGIT: 20 Gy na superfície do aplicador.")
        c4.metric("Dose mín (Gy)", f"{dff['dose_Gy'].min():.2f}")
        c5.metric("Dose máx (Gy)", f"{dff['dose_Gy'].max():.2f}")

        st.divider()
        sec("Conformidade Dosimétrica (QA)")
        desv = dff["desvio_pct"].dropna()
        if desv.empty:
            st.warning("Sem dados de desvio da prescrição para calcular conformidade.")
        else:
            tol = LIT["conformidade_alvo_pct"]
            dentro_3 = (desv.abs() <= tol).mean() * 100
            dentro_5 = (desv.abs() <= 5).mean() * 100
            mad = desv.abs().mean()
            fora = (desv.abs() > tol).sum()

            k1, k2, k3 = st.columns(3)
            k1.metric(f"Dentro de ±{tol:.0f}%", f"{dentro_3:.1f}%")
            k2.metric("Dentro de ±5%", f"{dentro_5:.1f}%")
            k3.metric("Desvio absoluto médio", f"{mad:.2f}%")

            if fora:
                st.warning(f"⚠️ **{fora}** de {len(desv)} tratamento(s) com desvio > ±{tol:.0f}% "
                           "— revisar registro dosimétrico.")
            else:
                st.success(f"Todos os {len(desv)} tratamentos dentro de ±{tol:.0f}% da prescrição.")

            st.bar_chart(desv.value_counts().sort_index())

        st.info(
            f"📚 **Atenuação em profundidade (literatura)** — fonte de fótons de "
            f"**{LIT['fonte_kV']} kV**; **{LIT['dose_superficie_Gy']:.0f} Gy** na superfície "
            f"atenuam para **{LIT['dose_1cm_Gy'][0]}–{LIT['dose_1cm_Gy'][1]} Gy a 1 cm** e "
            f"≈**{LIT['dose_2cm_Gy']} Gy a 2 cm** (aplicador de 4 cm)."
        )

    # ── Volume-Alvo ──────────────────────────────────────────────────────────
    with tab3:
        sec("Volume-Alvo Esférico Estimado")
        st.caption("Modelo de PTV esférico V = 4/3·π·r³ a partir do diâmetro do aplicador "
                   "(Schwid et al., JACMP 2017).")
        vol = dff["volume_cm3"].dropna()
        if vol.empty:
            st.warning("Sem dados de tamanho de aplicador para estimar o volume-alvo.")
        else:
            v1, v2, v3 = st.columns(3)
            v1.metric("Volume médio (cm³)", f"{vol.mean():.1f}")
            v2.metric("Volume mín (cm³)", f"{vol.min():.1f}")
            v3.metric("Volume máx (cm³)", f"{vol.max():.1f}")

            st.divider()
            por_apl = (
                dff.dropna(subset=["aplicador_cm"])
                .groupby("aplicador_cm")
                .agg(n=("aplicador_cm", "size"), volume_cm3=("volume_cm3", "first"))
                .reset_index()
            )
            por_apl["aplicador_cm"] = por_apl["aplicador_cm"].map(lambda x: f"{x:.1f} cm")
            por_apl["volume_cm3"] = por_apl["volume_cm3"].round(1)
            por_apl.columns = ["Aplicador", "Nº tratamentos", "Volume-alvo (cm³)"]
            st.dataframe(por_apl, use_container_width=True, hide_index=True)

    # ── Tendência Temporal ───────────────────────────────────────────────────
    with tab4:
        sec("Volume de Tratamentos ao Longo do Tempo")
        por_mes = dff.dropna(subset=["data_proc"]).groupby("mes_ano").size()
        if por_mes.empty:
            st.warning("Sem datas válidas para análise temporal.")
        else:
            t1, t2 = st.columns(2)
            with t1:
                st.caption("Tratamentos por mês")
                st.bar_chart(por_mes)
            with t2:
                st.caption("Acumulado")
                st.line_chart(por_mes.cumsum())

            st.divider()
            sec("Curva de Aprendizado — Desvio Médio por Ano")
            st.caption("Desvio absoluto médio da prescrição por ano. Tendência de queda "
                       "indica ganho de consistência dosimétrica com a experiência.")
            tmp = dff.dropna(subset=["ano", "desvio_pct"]).copy()
            if tmp.empty:
                st.info("Sem dados de desvio da prescrição por ano nos registros lidos.")
            else:
                tmp["abs_desvio"] = tmp["desvio_pct"].abs()
                por_ano = (
                    tmp.groupby("ano")
                    .agg(n=("abs_desvio", "size"), desvio_medio=("abs_desvio", "mean"),
                         desvio_max=("abs_desvio", "max"))
                    .reset_index()
                )
                por_ano["ano"] = por_ano["ano"].astype(str)
                tabela = por_ano.copy()
                tabela.columns = ["Ano", "Nº tratamentos", "Desvio abs. médio (%)", "Desvio abs. máx (%)"]
                tabela["Desvio abs. médio (%)"] = tabela["Desvio abs. médio (%)"].round(3)
                tabela["Desvio abs. máx (%)"] = tabela["Desvio abs. máx (%)"].round(3)
                st.dataframe(tabela, use_container_width=True, hide_index=True)

                if por_ano["desvio_max"].max() < 0.05:
                    st.success(
                        f"Desvios praticamente nulos (≈0%) em todos os {len(por_ano)} ano(s) — "
                        "a dose entregue coincide com a prescrita, então não há variação para "
                        "desenhar uma curva de aprendizado. Isso indica entrega dosimétrica "
                        "consistente."
                    )
                elif len(por_ano) < 2:
                    st.info(f"Apenas um ano com dados ({por_ano['ano'].iloc[0]}). A curva de "
                            "aprendizado precisa de ≥2 anos para mostrar tendência.")
                else:
                    st.bar_chart(por_ano.set_index("ano")["desvio_medio"])

    # ── Esterilizações ───────────────────────────────────────────────────────
    with tab5:
        sec("Esterilizações por Aplicador Serial")
        if "Applicator Serial Number" in dff.columns:
            ap_ser = (
                dff.groupby("Applicator Serial Number")["esteril"]
                .max()
                .sort_values(ascending=False)
                .reset_index()
            )
            ap_ser.columns = ["Serial do Aplicador", "Esterilizações (máx)"]
            st.dataframe(ap_ser, use_container_width=True, hide_index=True)
            esteril_total = dff["esteril"].dropna()
            if not esteril_total.empty:
                e1, e2 = st.columns(2)
                e1.metric("Esterilizações acumuladas (máx)", f"{int(esteril_total.max())}")
                e2.metric("Aplicadores distintos", f"{ap_ser['Serial do Aplicador'].nunique()}")
                st.caption("Acompanhe a vida útil dos aplicadores: contagens elevadas indicam "
                           "necessidade de inspeção/substituição conforme orientação do fabricante.")


def _pendencias_detalhe(dm):
    """Tabela de revisão pasta a pasta: status preciso de cada arquivo e o que falta."""
    rows = []
    for _, r in dm.iterrows():
        pdf_ok = r.get("pdf_ok") == True
        doc_ok = r.get("doc_ok") == True
        pm = str(r.get("pdf_motivo") or ("ok" if pdf_ok else "revisar"))
        dm_ = str(r.get("doc_motivo") or ("ok" if doc_ok else "revisar"))
        falta = [x for x, ok in (("PDF", pdf_ok), ("DOC", doc_ok)) if not ok]
        rows.append({
            "Nº": r.get("folder_number", ""),
            "Pasta": str(r.get("folder_name") or r.get("nome") or "").split("\\")[-1],
            "Paciente": r.get("nome", ""),
            "Patient ID": _fmt_pid(r.get("Patient ID")),
            "Status PDF": pm,
            "Status DOC": dm_,
            "Falta / Revisar": " e ".join(falta) if falta else "—",
        })
    out = pd.DataFrame(rows)
    return out.sort_values("Nº") if "Nº" in out.columns and not out.empty else out


def page_pendencias():
    sec("Pendências — Pastas para Revisar (PDF/DOC ausente ou nome divergente)")

    if df_miss.empty:
        st.success("Nenhuma pendência — toda pasta tem PDF e DOC com o nome da paciente.")
        return

    det = _pendencias_detalhe(df_miss)
    st.warning(f"**{len(det)}** pasta(s) para revisar, uma a uma:")
    st.caption("**REVISAR** = arquivo ausente **ou** com o nome da paciente não conferido. "
               "Arquivos escaneados/sem texto não entram aqui (assumidos OK). A coluna "
               "**Detalhe** traz a observação da leitura.")
    st.dataframe(det, use_container_width=True, hide_index=True)

    st.divider()
    csv = det.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar pendências detalhadas (CSV)", data=csv,
                       file_name="iort_pendencias.csv", mime="text/csv")


def page_literatura():
    sec("Literatura & Benchmark — TARGIT-IORT / INTRABEAM")

    st.markdown(
        '<div class="card" style="margin-bottom:18px;">'
        '<b>INTRABEAM (Carl Zeiss Meditec)</b> — sistema de radioterapia intraoperatória que '
        f'emite fótons de baixa energia ({LIT["fonte_kV"]} kV) a partir de uma fonte pontual no '
        'centro de um aplicador esférico. Na técnica <b>TARGIT-IORT</b> (radioterapia '
        'intraoperatória dirigida), uma dose única é entregue ao leito tumoral durante a '
        'cirurgia conservadora da mama. Esta página correlaciona os indicadores do serviço com '
        'os valores de referência publicados.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Benchmark: serviço × literatura ──────────────────────────────────────
    sec("Indicadores do Serviço × Referência da Literatura")
    st.caption("Cada linha contrasta o **valor amostrado neste serviço** com o **valor "
               "publicado** e traz um veredito de concordância. Os números entre colchetes "
               "remetem às **Referências** no fim da página.")
    apl_validos = dff["aplicador_cm"].dropna()
    desv = dff["desvio_pct"].dropna()
    vol = dff["volume_cm3"].dropna()
    dose = dff["dose_Gy"].dropna()

    dose_serv = f"{dose.mean():.2f} Gy" if not dose.empty else "—"
    apl_serv = (f"{apl_validos.min():.1f}–{apl_validos.max():.1f} cm (mediana {apl_validos.median():.1f})"
                if not apl_validos.empty else "—")
    conf_serv = f"{(desv.abs() <= LIT['conformidade_alvo_pct']).mean() * 100:.0f}%" if not desv.empty else "—"

    # ── Vereditos de concordância calculados a partir dos dados amostrados ─────
    if not dose.empty:
        _delta = abs(dose.mean() - LIT["dose_superficie_Gy"]) / LIT["dose_superficie_Gy"] * 100
        dose_ok = f"✓ concorda (Δ {_delta:.1f}%)" if _delta <= 5 else f"⚠️ Δ {_delta:.1f}% vs prescrição"
    else:
        dose_ok = "— sem dados"

    if not apl_validos.empty:
        _fora = int(((apl_validos < LIT["aplicador_min_cm"]) |
                     (apl_validos > LIT["aplicador_max_cm"])).sum())
        apl_ok = "✓ todos na faixa" if _fora == 0 else f"⚠️ {_fora} fora de 1,5–5,0 cm"
        _pct_comuns = apl_validos.isin(LIT["aplicadores_comuns"]).mean() * 100
        comuns_serv = f"{_pct_comuns:.0f}% usam 3,5/4,0 cm"
        comuns_ok = "✓ alinhado às séries" if _pct_comuns >= 50 else "ℹ️ perfil próprio do serviço"
    else:
        apl_ok = comuns_serv = comuns_ok = "— sem dados"

    if not vol.empty:
        vol_serv = f"{vol.min():.1f}–{vol.max():.1f} cm³ (média {vol.mean():.1f})"
        vol_ok = "✓ modelo esférico"
    else:
        vol_serv = vol_ok = "— sem dados"

    if not desv.empty:
        _dentro = (desv.abs() <= LIT["conformidade_alvo_pct"]).mean() * 100
        conf_ok = f"✓ {_dentro:.0f}% dentro de ±{LIT['conformidade_alvo_pct']:.0f}%" if _dentro >= 95 \
            else f"⚠️ {_dentro:.0f}% dentro de ±{LIT['conformidade_alvo_pct']:.0f}%"
    else:
        conf_ok = "— sem dados"

    bench = pd.DataFrame([
        ["Energia da fonte", f"{LIT['fonte_kV']} kV (padrão do sistema)",
         f"{LIT['fonte_kV']} kV", "✓ padrão do sistema", "[4]"],
        ["Dose na superfície", dose_serv,
         f"{LIT['dose_superficie_Gy']:.0f} Gy (prescrição TARGIT)", dose_ok, "[1][2]"],
        ["Dose a 1 cm de profundidade", "estimada por dosimetria",
         f"{LIT['dose_1cm_Gy'][0]}–{LIT['dose_1cm_Gy'][1]} Gy", "contexto dosimétrico", "[4]"],
        ["Faixa de aplicadores", apl_serv,
         f"{LIT['aplicador_min_cm']:.1f}–{LIT['aplicador_max_cm']:.1f} cm "
         f"(passo {LIT['aplicador_incr_cm']:.1f})", apl_ok, "[4]"],
        ["Aplicadores mais usados", comuns_serv,
         "3,5 e 4,0 cm (mais comuns em séries)", comuns_ok, "[4]"],
        ["Volume-alvo (PTV esférico)", vol_serv,
         "V = 4/3·π·r³ (modelo esférico)", vol_ok, "[5]"],
        [f"Conformidade (±{LIT['conformidade_alvo_pct']:.0f}%)", conf_serv,
         "meta interna de QA", conf_ok, "—"],
    ], columns=["Indicador", "Serviço (amostra)", "Literatura / Referência",
                "Concordância", "Ref."])
    st.dataframe(bench, use_container_width=True, hide_index=True)

    # ── Desfechos clínicos TARGIT-A ──────────────────────────────────────────
    sec("Desfechos Clínicos — Ensaio TARGIT-A")
    o1, o2 = st.columns(2)
    with o1:
        st.markdown(
            '<div class="card">'
            '<b>5 anos (Lancet 2014) [2]</b><br>'
            f'Recidiva local: <b>{LIT["targit_lr_5a"][0]}%</b> (TARGIT-IORT) vs '
            f'<b>{LIT["targit_lr_5a"][1]}%</b> (radioterapia externa). '
            'Resultado <b>não-inferior</b> dentro da margem pré-definida, em pacientes '
            'selecionadas de baixo risco.'
            '</div>',
            unsafe_allow_html=True,
        )
    with o2:
        st.markdown(
            '<div class="card">'
            '<b>Longo prazo (BMJ 2020, mediana 8,6 anos) [3]</b><br>'
            'Sem diferença estatisticamente significativa em sobrevida livre de recidiva local '
            '(HR 1,13), sobrevida global ou mortalidade por câncer de mama, com menos óbitos por '
            'causas não relacionadas ao câncer no grupo TARGIT-IORT.'
            '</div>',
            unsafe_allow_html=True,
        )
    st.caption("Os desfechos clínicos referem-se à população do ensaio TARGIT-A e servem como "
               "contexto; não são calculados a partir dos dados deste serviço.")

    # ── Referências ──────────────────────────────────────────────────────────
    sec("Referências")
    st.caption("Os marcadores [n] na tabela de indicadores e nos cartões acima remetem a esta lista.")
    for i, (txt, url) in enumerate(REFERENCIAS, start=1):
        st.markdown(f"**[{i}]** {txt} [🔗]({url})")


def page_diagnostico():
    sec("Diagnóstico — Leitura das Pastas")
    st.caption("Todas as pacientes detectadas (já sem duplicados). Use para conferir a "
               "contagem e achar pastas que não deveriam contar como tratamento.")

    pid_col = "Patient ID" if "Patient ID" in df.columns else None
    if pid_col:
        _pidstr = df[pid_col].astype(str).str.strip().str.lower().fillna("")
        has_id = ~_pidstr.isin(["", "nan", "none"])
    else:
        has_id = pd.Series(False, index=df.index)
    com_id = int(has_id.sum())
    com_pdf = int(df["pdf_ok"].eq(True).sum())
    com_doc = int(df["doc_ok"].eq(True).sum())
    completo = int((df["pdf_ok"].eq(True) & df["doc_ok"].eq(True)).sum())
    pend = len(pendencias_df(df))

    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes (sem duplicar)", len(df))
    c2.metric("Com relatório INTRABEAM", com_id)
    c3.metric("Sem relatório INTRABEAM", len(df) - com_id)
    c4, c5, c6 = st.columns(3)
    c4.metric("Completos (PDF+DOC)", completo)
    c5.metric("Com DOC (nome)", com_doc)
    c6.metric("Pendências", pend)

    st.divider()
    f1, f2 = st.columns([2, 1])
    with f1:
        busca = st.text_input("🔍 Buscar pasta / nome / Patient ID", key="diag_busca")
    with f2:
        filtro = st.selectbox(
            "Mostrar", ["Todas", "Só pendências (incompletas)", "Só sem relatório INTRABEAM",
                        "Só completas"], key="diag_filtro")

    cols = ["folder_number", "folder_name", "Patient ID", "nome", "pdf_ok", "doc_ok",
            "quadrant_auto", "quadrant_auto_obs"]
    cols = [c for c in cols if c in df.columns]
    diag = df[cols].copy()

    if filtro == "Só pendências (incompletas)":
        diag = diag[~(df["pdf_ok"].eq(True) & df["doc_ok"].eq(True))]
    elif filtro == "Só sem relatório INTRABEAM" and pid_col:
        diag = diag[~has_id]
    elif filtro == "Só completas":
        diag = diag[df["pdf_ok"].eq(True) & df["doc_ok"].eq(True)]
    if busca:
        m = diag.apply(lambda r: busca.lower() in str(r).lower(), axis=1)
        diag = diag[m]

    diag = diag.sort_values("folder_number") if "folder_number" in diag.columns else diag
    if "Patient ID" in diag.columns:
        diag["Patient ID"] = diag["Patient ID"].map(_fmt_pid)
    _lab = {"folder_number": "Nº", "folder_name": "Pasta", "Patient ID": "Patient ID",
            "nome": "Paciente", "pdf_ok": "PDF✓", "doc_ok": "DOC✓",
            "quadrant_auto": "Quadrante", "quadrant_auto_obs": "Observação"}
    show = diag.rename(columns=_lab)
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.caption(f"{len(diag)} de {len(df)} paciente(s) exibida(s).")

    st.download_button(
        "⬇️ Baixar diagnóstico completo (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="iort_diagnostico.csv", mime="text/csv")


# ── Router ─────────────────────────────────────────────────────────────────────
if pagina == "Análise":
    page_dashboard()          # visão geral (antiga aba Dashboard)
    st.divider()
    page_analise()
elif pagina == "Tratamentos":
    page_tratamentos()
elif pagina == "Literatura":
    page_literatura()
elif pagina == "Pendências":
    page_pendencias()
    st.divider()
    page_diagnostico()        # diagnóstico das pastas (antiga aba Diagnóstico)
