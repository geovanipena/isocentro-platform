"""
SRS Analysis – Avaliação Dosimétrica de Radiocirurgia
Versão Streamlit  |  Física Médica / Radioterapia
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io
import os
import math
import re
import unicodedata
import csv
import base64
from datetime import datetime, date
from pathlib import Path

try:
    import pydicom
    PYDICOM_OK = True
except ImportError:
    PYDICOM_OK = False

try:
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors as rl_colors
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SRS Analysis",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORICO_PATH = DATA_DIR / "historico.csv"
MEDICOS_PATH   = DATA_DIR / "medicos.txt"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F1F3D 0%, #1B3A6B 100%);
    border-right: none;
}
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
[data-testid="stSidebar"] .stMarkdown hr { border-color: rgba(255,255,255,.15); margin:.4rem 0; }

.main .block-container { padding-top:1.2rem; padding-bottom:2rem; max-width:1400px; }

.srs-header { display:flex; align-items:center; gap:14px; margin-bottom:.2rem; }
.srs-header .icon-box {
    width:48px; height:48px;
    background: linear-gradient(135deg,#1B3A6B,#2563EB);
    border-radius:12px; display:flex; align-items:center; justify-content:center;
    font-size:1.6rem; flex-shrink:0; box-shadow:0 4px 14px rgba(37,99,235,.35);
}
.srs-header h1 { font-size:1.55rem !important; font-weight:700 !important;
    color:#0F1F3D !important; margin:0 !important; line-height:1.2 !important; }
.srs-header .sub { font-size:.8rem; color:#64748B; font-weight:400; margin-top:2px; }

.sec { border-left:4px solid #2563EB; padding-left:12px; margin:14px 0 10px 0; }
.sec h3 { margin:0; font-size:14px; font-weight:600; color:#1B3A6B; }

.card {
    background:#fff; border:1px solid #E2E8F0; border-radius:10px;
    padding:14px 16px; box-shadow:0 1px 4px rgba(0,0,0,.06); margin-bottom:8px;
}

.result-row {
    display:flex; align-items:center; padding:6px 10px;
    border-radius:7px; background:#F8FAFC; border:1px solid #E2E8F0; margin-bottom:4px;
}
.result-row .rname { flex:1; font-size:12.5px; color:#334155; }
.result-row .rval  { font-size:14px; font-weight:700; color:#1B3A6B; min-width:55px; text-align:right; margin-right:8px; }
.result-row .rcls  { font-size:11px; font-weight:600; padding:2px 8px; border-radius:4px; }

.cls-EXCELENTE    { background:#DBEAFE; color:#1D4ED8; }
.cls-ACEITAVEL    { background:#DCFCE7; color:#15803D; }
.cls-SATISFATORIO { background:#DCFCE7; color:#15803D; }
.cls-LIMIAR       { background:#FEF3C7; color:#B45309; }
.cls-INSATISFATORIO { background:#FEE2E2; color:#DC2626; }
.cls-INACEITAVEL  { background:#FEE2E2; color:#DC2626; }
.cls-NA           { background:#F1F5F9; color:#64748B; }

.stTabs [data-baseweb="tab-list"] {
    background:#F8FAFC; border-radius:8px; padding:4px; gap:4px;
}
.stTabs [data-baseweb="tab"] {
    background:transparent; border-radius:6px; color:#475569;
    font-weight:500; padding:7px 16px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg,#1B3A6B,#2563EB) !important;
    color:#fff !important; box-shadow:0 2px 8px rgba(37,99,235,.3);
}

.warn { background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px;
    padding:8px 12px; font-size:12.5px; color:#92400E; margin-bottom:8px; }
.info { background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px;
    padding:8px 12px; font-size:12.5px; color:#1E40AF; margin-bottom:8px; }
.ok   { background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px;
    padding:8px 12px; font-size:12.5px; color:#15803D; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

# ── Physics engine ─────────────────────────────────────────────────────────────

def _reff_cm(volume_cc: float) -> float:
    if not volume_cc or volume_cc <= 0:
        return float("nan")
    return (3.0 * volume_cc / (4.0 * math.pi)) ** (1.0 / 3.0)

_DGI_TABLE = [
    ((0.0,  1.0),  91, 83),
    ((1.0,  3.0),  81, 72),
    ((3.0,  5.0),  74, 65),
    ((5.0, 10.0),  70, 58),
    ((10.0,15.0),  65, 52),
    ((15.0,40.0),  52, 35),
]

def _limiares_dgi(tv_cc):
    if not tv_cc or tv_cc <= 0:
        return None, None
    for (lo, hi), ideal, minimo in _DGI_TABLE:
        if lo <= tv_cc <= hi:
            return ideal, minimo
    return (_DGI_TABLE[0][1], _DGI_TABLE[0][2]) if tv_cc < _DGI_TABLE[0][0][0] else \
           (_DGI_TABLE[-1][1], _DGI_TABLE[-1][2])

def _classificar_dgi(val: float, tv_cc) -> str:
    ideal, minimo = _limiares_dgi(tv_cc)
    if ideal is None or not np.isfinite(val):
        return "N/A"
    if val >= ideal:   return "EXCELENTE"
    if val >= minimo:  return "ACEITÁVEL"
    return "INSATISFATÓRIO"


class AvaliacaoPlanejamentoSRS:
    def __init__(self, tv, tvpiv, vd50, piv, dmin98, dmax2, d50, dptv):
        self.tv = tv; self.tvpiv = tvpiv; self.vd50 = vd50; self.piv = piv
        self.dmin98 = dmin98; self.dmax2 = dmax2; self.d50 = d50; self.dptv = dptv

    def _ci_rtog(self):
        return self.piv / self.tv if self.tv > 0 else float("nan")

    def _pci(self):
        return (self.tvpiv**2) / (self.tv * self.piv) if self.tv > 0 and self.piv > 0 else float("nan")

    def _q(self):
        return self.dmin98 / self.dptv if self.dptv > 0 else float("nan")

    def _cvi(self):
        return self.tvpiv / self.tv if self.tv > 0 else float("nan")

    def _hi_rtog(self):
        return self.dmax2 / self.dptv if self.dptv > 0 else float("nan")

    def _hi_icru83(self):
        return (self.dmax2 - self.dmin98) / self.d50 if self.d50 > 0 else float("nan")

    def _gi(self):
        return self.vd50 / self.piv if self.piv > 0 else float("nan")

    def _dgi(self):
        if self.piv > 0 and self.vd50 > 0:
            reff_rx = _reff_cm(self.piv)
            reff_50 = _reff_cm(self.vd50)
            return (100.0 - 100.0 * ((reff_50 - reff_rx) - 0.3)) / 100
        return float("nan")

    def analise_completa(self):
        return {
            "CI_RTOG":   self._ci_rtog(),
            "PCI":       self._pci(),
            "Q":         self._q(),
            "CVI":       self._cvi(),
            "HI_RTOG":   self._hi_rtog(),
            "HI_ICRU83": self._hi_icru83(),
            "GI":        self._gi(),
            "DGI":       self._dgi(),
        }


INDEX_LABELS = {
    "CI_RTOG":   "Conformidade (CI RTOG)",
    "PCI":       "Conformidade Paddick (PCI)",
    "Q":         "Qualidade de Cobertura (Q)",
    "CVI":       "Cobertura (CVI)",
    "HI_RTOG":   "Homogeneidade (HI RTOG 9005)",
    "HI_ICRU83": "Homogeneidade (ICRU 83)",
    "GI":        "Gradiente (GI)",
    "DGI":       "Gradiente de Dose (DGI)",
}


def classificar_indice(key: str, val: float, tv_cc=None) -> str:
    if not np.isfinite(val):
        return "N/A"
    if key == "CI_RTOG":
        if 1 <= val <= 2:                          return "EXCELENTE"
        if (0.9 <= val < 1) or (2 < val <= 2.5):  return "ACEITÁVEL"
        return "INACEITÁVEL"
    if key == "PCI":
        if val >= 0.8:          return "EXCELENTE"
        if 0.6 <= val < 0.8:   return "SATISFATÓRIO"
        if 0.5 <= val < 0.6:   return "LIMIAR"
        return "INSATISFATÓRIO"
    if key == "Q":
        if val >= 0.9:          return "EXCELENTE"
        if 0.8 <= val < 0.9:   return "ACEITÁVEL"
        return "INACEITÁVEL"
    if key == "CVI":
        if val >= 0.95:         return "EXCELENTE"
        if 0.9 <= val < 0.95:  return "SATISFATÓRIO"
        return "INSATISFATÓRIO"
    if key == "HI_RTOG":
        if val <= 2:            return "EXCELENTE"
        if 2 < val <= 2.5:     return "SATISFATÓRIO"
        return "LIMIAR"
    if key == "HI_ICRU83":
        if 1.0 <= val <= 1.1:  return "EXCELENTE"
        if 1.1 < val <= 1.2:   return "SATISFATÓRIO"
        return "INSATISFATÓRIO"
    if key == "GI":
        if val <= 3:            return "EXCELENTE"
        if 3 < val <= 4:       return "SATISFATÓRIO"
        return "INSATISFATÓRIO"
    if key == "DGI":
        return _classificar_dgi(val, tv_cc)
    return "N/A"


def _categoria_base(s: str) -> str:
    s = (s or "").upper()
    for b in ("EXCELENTE","ACEITÁVEL","SATISFATÓRIO","LIMIAR","INSATISFATÓRIO","INACEITÁVEL","N/A"):
        if s.startswith(b) or b in s:
            return b
    return "N/A"


CLS_CSS = {
    "EXCELENTE":    "cls-EXCELENTE",
    "ACEITÁVEL":    "cls-ACEITAVEL",
    "SATISFATÓRIO": "cls-SATISFATORIO",
    "LIMIAR":       "cls-LIMIAR",
    "INSATISFATÓRIO":"cls-INSATISFATORIO",
    "INACEITÁVEL":  "cls-INACEITAVEL",
    "N/A":          "cls-NA",
}

CLS_COLOR = {
    "EXCELENTE":    "#1D4ED8",
    "ACEITÁVEL":    "#15803D",
    "SATISFATÓRIO": "#15803D",
    "LIMIAR":       "#B45309",
    "INSATISFATÓRIO":"#DC2626",
    "INACEITÁVEL":  "#DC2626",
    "N/A":          "#64748B",
}

# ── DICOM parsing ──────────────────────────────────────────────────────────────

def _parse_dvh_pairs(dvh):
    """Returns (doses_Gy_array, vols_raw_array, units_str)."""
    n = int(getattr(dvh, "DVHNumberOfBins", 0))
    if n <= 0:
        raise ValueError("DVHNumberOfBins inválido.")

    dmin_raw = float(getattr(dvh, "DVHMinimumDose", 0.0))
    dmax_raw = float(getattr(dvh, "DVHMaximumDose", 0.0))
    binw_raw = getattr(dvh, "DVHDoseBinWidth", None)
    binw_raw = float(binw_raw) if binw_raw is not None else None
    dose_scaling = float(getattr(dvh, "DVHDoseScaling", 1.0))
    units = (getattr(dvh, "DVHVolumeUnits", "") or "").upper().strip()

    raw = getattr(dvh, "DVHData", "")
    if isinstance(raw, bytes):
        raw = raw.decode(errors="ignore")
    vals = [float(v) for v in raw.split("\\")] if isinstance(raw, str) else list(raw or [])

    if len(vals) >= 2 * n:
        doses_raw = np.array(vals[0::2][:n], dtype=float)
        vols_raw  = np.array(vals[1::2][:n], dtype=float)
    elif len(vals) >= n:
        vols_raw = np.array(vals[:n], dtype=float)
        if binw_raw is not None:
            doses_raw = dmin_raw + np.arange(n) * binw_raw
        elif dmax_raw > dmin_raw:
            doses_raw = np.linspace(dmin_raw, dmax_raw, n)
        else:
            doses_raw = np.arange(n, dtype=float)
    else:
        raise ValueError("DVHData inconsistente com DVHNumberOfBins.")

    cand = {
        "as_is":     doses_raw.copy(),
        "*scaling":  doses_raw * dose_scaling,
        "*dmax/100": doses_raw * (dmax_raw / 100.0) if dmax_raw else doses_raw.copy(),
    }
    if np.max(doses_raw) > 0 and dmax_raw:
        cand["*dmax"] = doses_raw * dmax_raw
    if dmax_raw > dmin_raw:
        cand["linspace"] = np.linspace(dmin_raw, dmax_raw, n)

    def _score(arr):
        mx = float(np.max(arr)) if arr.size else np.inf
        return abs(mx - dmax_raw)

    best = min(cand, key=lambda k: _score(cand[k]))
    doses_gy = np.asarray(cand[best], dtype=float)

    if np.any(np.diff(doses_gy) < 0):
        order = np.argsort(doses_gy)
        doses_gy = doses_gy[order]
        vols_raw  = vols_raw[order]

    return doses_gy, vols_raw, units


def obter_volume_roi_cc(dvh):
    ref = getattr(dvh, "DVHReferencedROISequence", [None])[0]
    if ref and hasattr(ref, "DVHROIVolume"):
        try:
            v = float(ref.DVHROIVolume)
            if v > 0:
                return v
        except Exception:
            pass
    doses, vols, units = _parse_dvh_pairs(dvh)
    if units in ("CM3", "CC", "CM^3"):
        return float(vols[0])
    return None


def Vx_cc(dvh, x_gy, vtotal_cc=None):
    doses, vols, units = _parse_dvh_pairs(dvh)
    vi = float(np.interp(float(x_gy), doses, vols))
    if units in ("CM3", "CC", "CM^3"):
        return vi
    if units in ("PERCENT", "RELATIVE"):
        vtot = vtotal_cc or obter_volume_roi_cc(dvh)
        if not vtot:
            raise ValueError("vtotal_cc necessário para DVH relativo.")
        return vi * vtot / 100.0
    raise ValueError(f"Unidade DVH desconhecida: {units}")


def Vx_percent(dvh, x_gy):
    doses, vols, units = _parse_dvh_pairs(dvh)
    vi = float(np.interp(float(x_gy), doses, vols))
    if units in ("PERCENT", "RELATIVE"):
        pct = vi
    elif units in ("CM3", "CC", "CM^3"):
        vtot = obter_volume_roi_cc(dvh)
        pct = (vi / vtot * 100.0) if vtot and vtot > 0 else float("nan")
    else:
        return float("nan")
    return max(0.0, min(100.0, pct)) if np.isfinite(pct) else float("nan")


def Dv_gy(dvh, v_percent):
    try:
        doses, vols, units = _parse_dvh_pairs(dvh)
    except Exception:
        return float("nan")
    doses = np.asarray(doses, float); vols = np.asarray(vols, float)
    if units in ("CM3", "CC", "CM^3"):
        vols_cc = vols
    elif units in ("PERCENT", "RELATIVE"):
        tv = obter_volume_roi_cc(dvh)
        if not tv or not np.isfinite(tv) or tv <= 0:
            return float("nan")
        vols_cc = vols * float(tv) / 100.0
    else:
        return float("nan")
    if np.any(np.diff(doses) < 0):
        idx = np.argsort(doses)
        doses, vols_cc = doses[idx], vols_cc[idx]
    if vols_cc.size and vols_cc[0] < vols_cc[-1]:
        doses, vols_cc = doses[::-1], vols_cc[::-1]
    if not len(doses) or vols_cc[0] <= 0:
        return float("nan")
    alvo = (float(v_percent) / 100.0) * float(vols_cc[0])
    return float(np.interp(alvo, vols_cc[::-1], doses[::-1]))


def dose_media_gy(dvh):
    doses, vols, units = _parse_dvh_pairs(dvh)
    doses = np.asarray(doses, float); vols = np.asarray(vols, float)
    if units in ("PERCENT", "RELATIVE"):
        y = np.clip(vols / 100.0, 0.0, 1.0)
    elif units in ("CM3", "CC", "CM^3"):
        vtot = obter_volume_roi_cc(dvh)
        if not vtot or vtot <= 0:
            return float("nan")
        y = np.clip(vols / float(vtot), 0.0, 1.0)
    else:
        return float("nan")
    if not len(doses):
        return float("nan")
    if np.any(np.diff(doses) < 0):
        order = np.argsort(doses); doses, y = doses[order], y[order]
    if y[0] < y[-1]:
        y, doses = y[::-1], doses[::-1]
    return float(np.trapz(y, doses))


def _norm_roi(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ASCII","ignore").decode("ASCII").upper()
    return re.sub(r"\s+", " ", re.sub(r"[._\-]+", " ", s)).strip()


def encontrar_dvh_por_nome(ds_rd, ds_rs, consulta: str):
    try:
        roi_dict = {r.ROINumber: r.ROIName for r in getattr(ds_rs,"StructureSetROISequence",[])}
        dvh_list = getattr(ds_rd, "DVHSequence", [])
    except Exception:
        return None, None
    qn = _norm_roi(consulta)
    candidatos = []
    for dvh in dvh_list:
        try:
            rno = dvh.DVHReferencedROISequence[0].ReferencedROINumber
            nome = roi_dict.get(rno, f"ROI {rno}")
            candidatos.append((dvh, nome))
        except Exception:
            continue
    for dvh, nome in candidatos:
        if _norm_roi(nome) == qn: return dvh, nome
    for dvh, nome in candidatos:
        if qn in _norm_roi(nome):  return dvh, nome
    return None, None

# ── Name helpers ───────────────────────────────────────────────────────────────

def formatar_nome(nome: str) -> str:
    preposicoes = {"da","de","do","das","dos","e"}
    return " ".join(p.lower() if p.lower() in preposicoes else p.capitalize()
                    for p in nome.strip().split())


def formatar_nome_dicom(pn) -> str:
    try:
        given  = (getattr(pn, "given_name",  "") or "").strip()
        middle = (getattr(pn, "middle_name", "") or "").strip()
        family = (getattr(pn, "family_name", "") or "").strip()
        if given or middle or family:
            return formatar_nome(" ".join(p for p in [given, middle, family] if p))
    except Exception:
        pass
    s = str(pn or "")
    if "^" in s:
        pts = s.split("^")
        s = " ".join(p.strip() for p in [pts[1] if len(pts)>1 else "", pts[2] if len(pts)>2 else "", pts[0]] if p.strip())
    return formatar_nome(s.replace("^"," ").strip())

# ── Data storage ───────────────────────────────────────────────────────────────

def _carregar_medicos() -> list:
    if MEDICOS_PATH.exists():
        return sorted({m.strip() for m in MEDICOS_PATH.read_text(encoding="utf-8").splitlines() if m.strip()}, key=str.lower)
    return []


def _salvar_medicos(lista: list):
    MEDICOS_PATH.write_text("\n".join(sorted({m for m in lista if m}, key=str.lower)), encoding="utf-8")


def _carregar_historico() -> pd.DataFrame:
    if HISTORICO_PATH.exists() and HISTORICO_PATH.stat().st_size > 10:
        try:
            return pd.read_csv(HISTORICO_PATH, on_bad_lines="skip")
        except Exception:
            pass
    return pd.DataFrame()


def _salvar_linha_historico(row: dict):
    cols = list(row.keys())
    exists = HISTORICO_PATH.exists() and HISTORICO_PATH.stat().st_size > 10
    with open(HISTORICO_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow(row)

# ── DICOM validation ───────────────────────────────────────────────────────────

def _validar_coerencia(ds_rd, ds_rs, ds_rtplan) -> tuple:
    """Returns (ok: bool, errors: list, warnings: list)."""
    erros, avisos = [], []

    def _u(v): return str(v or "").strip()

    pid_rd = _u(getattr(ds_rd,      "PatientID", ""))
    pid_rs = _u(getattr(ds_rs,      "PatientID", ""))
    pid_rp = _u(getattr(ds_rtplan,  "PatientID", ""))

    if not all([pid_rd, pid_rs, pid_rp]):
        erros.append("PatientID ausente em um ou mais arquivos.")
    elif len({pid_rd, pid_rs, pid_rp}) > 1:
        erros.append(f"PatientID divergente: RD='{pid_rd}', RS='{pid_rs}', RTPLAN='{pid_rp}'.")

    rtplan_uid = _u(getattr(ds_rtplan, "SOPInstanceUID", ""))
    rd_refs = [_u(getattr(x, "ReferencedSOPInstanceUID",""))
               for x in getattr(ds_rd, "ReferencedRTPlanSequence", [])]
    if not rd_refs:
        erros.append("RTDOSE não possui ReferencedRTPlanSequence.")
    elif rtplan_uid and rtplan_uid not in rd_refs:
        erros.append("RTDOSE não referencia o RTPLAN selecionado.")

    rs_uid = _u(getattr(ds_rs, "SOPInstanceUID", ""))
    rp_rs_refs = [_u(getattr(x, "ReferencedSOPInstanceUID",""))
                  for x in getattr(ds_rtplan, "ReferencedStructureSetSequence", [])]
    if not rp_rs_refs:
        erros.append("RTPLAN não referencia nenhum RTSTRUCT.")
    elif rs_uid and rs_uid not in rp_rs_refs:
        erros.append("RTPLAN não referencia o RTSTRUCT selecionado.")

    siu = {_u(getattr(ds, "StudyInstanceUID",""))
           for ds in [ds_rd, ds_rs, ds_rtplan] if getattr(ds,"StudyInstanceUID",None)}
    if len(siu) > 1:
        avisos.append("StudyInstanceUID divergente (normal em alguns TPS).")

    return len(erros) == 0, erros, avisos

# ── DICOM import ───────────────────────────────────────────────────────────────

def _processar_dicom(files: list) -> dict | None:
    """
    Receives a list of 3 UploadedFile objects (RTDOSE, RTSTRUCT, RTPLAN in any order).
    Returns a dict with parsed data, or None on failure.
    """
    if not PYDICOM_OK:
        st.error("pydicom não está instalado. Execute: pip install pydicom")
        return None

    ds_rd = ds_rs = ds_rtplan = None
    mods = []
    try:
        for f in files:
            ds = pydicom.dcmread(io.BytesIO(f.read()), force=True, stop_before_pixels=True)
            mod = str(getattr(ds, "Modality", "")).upper().strip()
            mods.append((f.name, mod))
            if mod == "RTDOSE":   ds_rd      = ds
            elif mod == "RTSTRUCT": ds_rs    = ds
            elif mod == "RTPLAN":  ds_rtplan = ds

        if not all([ds_rd, ds_rs, ds_rtplan]):
            st.error("Selecione exatamente 1 RTDOSE, 1 RTSTRUCT e 1 RTPLAN.\n\n" +
                     "\n".join(f"– {n}: {m or '(sem Modality)'}" for n, m in mods))
            return None

        ok, erros, avisos = _validar_coerencia(ds_rd, ds_rs, ds_rtplan)
        if not ok:
            st.error("Arquivos incompatíveis:\n\n" + "\n".join(f"• {e}" for e in erros))
            return None
        for a in avisos:
            st.warning(f"Aviso: {a}")

    except Exception as e:
        st.error(f"Erro ao ler DICOM: {type(e).__name__}: {e}")
        return None

    # ── Paciente
    pn = getattr(ds_rs, "PatientName", "")
    nome = formatar_nome_dicom(pn)
    pid  = str(getattr(ds_rs, "PatientID", "")).strip()
    dob_raw = str(getattr(ds_rs, "PatientBirthDate", "")).strip()
    dob = f"{dob_raw[6:8]}/{dob_raw[4:6]}/{dob_raw[:4]}" if len(dob_raw) == 8 and dob_raw.isdigit() else ""

    # ── Plano
    num_frc = None; dose_total = None; dose_frc = None
    fg_seq = getattr(ds_rtplan, "FractionGroupSequence", [])
    if fg_seq:
        fg = fg_seq[0]
        num_frc = getattr(fg, "NumberOfFractionsPlanned", None)
        try:
            rb = getattr(fg, "ReferencedBeamSequence", [{}])[0]
            if hasattr(rb, "BeamDose"):
                dose_frc = float(rb.BeamDose)
        except Exception:
            pass

    for dr in getattr(ds_rtplan, "DoseReferenceSequence", []):
        if hasattr(dr, "TargetPrescriptionDose"):
            if getattr(dr, "DoseReferenceStructureType","").upper() == "TARGET":
                dose_total = float(dr.TargetPrescriptionDose); break
    if dose_total is None:
        dr_seq = getattr(ds_rtplan, "DoseReferenceSequence", [])
        if dr_seq and hasattr(dr_seq[0], "TargetPrescriptionDose"):
            dose_total = float(dr_seq[0].TargetPrescriptionDose)

    if dose_frc is None and dose_total and num_frc:
        try: dose_frc = float(dose_total) / float(num_frc)
        except Exception: pass

    # ── Médico
    med_raw = getattr(ds_rtplan, "PhysiciansOfRecord", "")
    try:
        pn0 = med_raw[0] if isinstance(med_raw, (list,tuple)) else med_raw
        medico = formatar_nome_dicom(pn0)
    except Exception:
        medico = str(med_raw).replace("^"," ").strip()

    # ── ROI dict e DVHs
    roi_dict = {r.ROINumber: r.ROIName for r in getattr(ds_rs,"StructureSetROISequence",[])}
    dvhs = []
    for dvh in getattr(ds_rd, "DVHSequence", []):
        try:
            rno  = dvh.DVHReferencedROISequence[0].ReferencedROINumber
            nome_roi = roi_dict.get(rno, f"ROI {rno}")
            doses, vols, units = _parse_dvh_pairs(dvh)
            vtot = obter_volume_roi_cc(dvh)
            dvhs.append({
                "nome": nome_roi, "doses": doses.tolist(), "vols": vols.tolist(),
                "units": units, "vtotal_cc": vtot, "dvh_obj": dvh
            })
        except Exception:
            continue

    dvhs.sort(key=lambda d: (_norm_roi(d["nome"])))

    return {
        "ds_rd": ds_rd, "ds_rs": ds_rs, "ds_rtplan": ds_rtplan,
        "paciente": {"nome": nome, "id": pid, "nascimento": dob, "medico": medico},
        "plano": {
            "num_frc":    int(num_frc) if num_frc else 1,
            "dose_frc":   round(float(dose_frc), 2) if dose_frc else 0.0,
            "dose_total": round(float(dose_total), 2) if dose_total else 0.0,
        },
        "dvhs": dvhs,
    }


def _autopreencher_cerebro(dvhs: list) -> dict:
    """Returns cerebro dict with auto-filled values from DICOM DVHs."""

    def _strip(s): return unicodedata.normalize("NFKD",s or "").encode("ASCII","ignore").decode("ASCII")
    def _norm(s):
        s = _strip(s).upper()
        return re.sub(r"\s+", " ", re.sub(r"[._\-]+", " ", s)).strip()

    def _is_brain_total(n):
        bad = [r"\bBRAIN\s*STEM\b",r"\bSTEM\b",r"\bTRONCO\b",r"\bCEREBELO\b",
               r"\bCEREBELLUM\b",r"\bEYE\b",r"\bOPTIC\b",r"\bLENS\b"]
        if any(re.search(p,n) for p in bad): return False
        return bool(re.search(r"\b(WHOLE\s*BRAIN|BRAIN|CEREBRO|CEREBRUM|ENCEFAL\w*)\b",n))

    def _is_minus_ptv(n):
        return any(re.search(p,n) for p in [
            r"\bMINUS\s*PTV\b",r"\bMENOS\s*PTV\b",r"\bBRAIN\s*PTV\b",
            r"\bCEREBRO\s*PTV\b",r"\bEX\s*PTV\b",r"\bSEM\s*PTV\b"])

    def _is_minus_gtv(n):
        return any(re.search(p,n) for p in [
            r"\bMINUS\s*GTV\b",r"\bMENOS\s*GTV\b",r"\bBRAIN\s*GTV\b",
            r"\bCEREBRO\s*GTV\b",r"\bEX\s*GTV\b",r"\bSEM\s*GTV\b"])

    brain_total = None; brain_m_ptv = None; brain_m_gtv = None
    brain_totals = []

    for d in dvhs:
        n = _norm(d["nome"])
        obj = d["dvh_obj"]
        if _is_brain_total(n) and not _is_minus_ptv(n) and not _is_minus_gtv(n):
            brain_totals.append((obj, obter_volume_roi_cc(obj)))
        if _is_minus_ptv(n): brain_m_ptv = obj
        if _is_minus_gtv(n): brain_m_gtv = obj

    if brain_totals:
        brain_totals.sort(key=lambda t: t[1] or 0, reverse=True)
        brain_total = brain_totals[0][0]

    def _safe(f, dvh, *a):
        try: v = f(dvh, *a); return round(v,2) if v and np.isfinite(v) else 0.0
        except Exception: return 0.0

    dvh_vx = brain_m_ptv or brain_m_gtv or brain_total
    return {
        "volume_cc":         round(float(obter_volume_roi_cc(brain_total) or 0), 1) if brain_total else 0.0,
        "minus_ptv_dmean":   _safe(dose_media_gy, brain_m_ptv) if brain_m_ptv else 0.0,
        "minus_gtv_dmean":   _safe(dose_media_gy, brain_m_gtv) if brain_m_gtv else 0.0,
        "v10_cc":            _safe(Vx_cc, dvh_vx, 10.0) if dvh_vx else 0.0,
        "v12_cc":            _safe(Vx_cc, dvh_vx, 12.0) if dvh_vx else 0.0,
        "v14_cc":            _safe(Vx_cc, dvh_vx, 14.0) if dvh_vx else 0.0,
    }


def _calcular_ptv_indices(dvh_ptv, ds_rd, ds_rs, dose_presc: float) -> dict:
    """Calculate all indices for a single PTV DVH object."""
    volume_ptv = obter_volume_roi_cc(dvh_ptv)
    if not volume_ptv or not np.isfinite(volume_ptv) or volume_ptv <= 0:
        raise ValueError("Não foi possível determinar o volume do PTV.")

    dvh_body, _ = encontrar_dvh_por_nome(ds_rd, ds_rs, "BODY") or (None, None)
    if dvh_body is None:
        dvh_body, _ = encontrar_dvh_por_nome(ds_rd, ds_rs, "EXTERNAL") or (None, None)

    piv_cc = vd50_cc = float("nan")
    if dvh_body is not None:
        vtot_body = obter_volume_roi_cc(dvh_body)
        if vtot_body and np.isfinite(vtot_body) and vtot_body > 0:
            piv_cc  = Vx_cc(dvh_body, dose_presc,     vtotal_cc=vtot_body)
            vd50_cc = Vx_cc(dvh_body, dose_presc/2.0, vtotal_cc=vtot_body)

    tvpiv_pct = Vx_percent(dvh_ptv, dose_presc)
    tvpiv_cc  = (tvpiv_pct / 100.0) * volume_ptv
    dmin98 = Dv_gy(dvh_ptv, 98)
    dmax2  = Dv_gy(dvh_ptv,  2)
    d50    = Dv_gy(dvh_ptv, 50)

    params = {"tv": volume_ptv, "tvpiv": tvpiv_cc, "vd50": vd50_cc, "piv": piv_cc,
              "dmin98": dmin98, "dmax2": dmax2, "d50": d50, "dptv": dose_presc}
    resultados = AvaliacaoPlanejamentoSRS(**params).analise_completa()
    return {"params": params, "resultados": resultados}

# ── PDF generation ─────────────────────────────────────────────────────────────

def _gerar_pdf(paciente, plano, cerebro, resultados_por_ptv) -> bytes | None:
    if not REPORTLAB_OK:
        return None

    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    def _draw_header():
        c.setFillColorRGB(0.06, 0.12, 0.24)
        c.rect(0, H - 70, W, 70, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, H - 38, "Relatório de Avaliação Dosimétrica de Radiocirurgia")
        c.setFont("Helvetica", 9)
        c.drawString(40, H - 55, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        c.setFillColorRGB(0, 0, 0)

    def _line(y, label, val, x1=50, x2=180):
        c.setFont("Helvetica-Bold", 9); c.drawString(x1, y, label)
        c.setFont("Helvetica", 9);      c.drawString(x2, y, str(val))
        return y - 14

    _draw_header()
    y = H - 95

    # Dados do paciente
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Dados do Paciente"); y -= 4
    c.setStrokeColorRGB(.8,.8,.8); c.line(40, y, W-40, y); y -= 12
    y = _line(y, "Paciente:",   paciente.get("nome",""))
    y = _line(y, "ID:",         paciente.get("id",""))
    y = _line(y, "Nascimento:", paciente.get("nascimento",""))
    y = _line(y, "Médico:",     paciente.get("medico",""))
    y = _line(y, "Frações:",    f"{plano.get('num_frc','')} × {plano.get('dose_frc','')} Gy = {plano.get('dose_total','')} Gy")

    y -= 10
    # Parâmetros cerebrais
    if any(v and float(v) > 0 for v in cerebro.values()):
        c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Parâmetros – Cérebro"); y -= 4
        c.line(40, y, W-40, y); y -= 12
        campos_cerebro = [
            ("Volume cerebral:",       f"{cerebro.get('volume_cc',0):.1f} cc"),
            ("Cérebro−PTV (Dmean):",   f"{cerebro.get('minus_ptv_dmean',0):.2f} Gy"),
            ("Cérebro−GTV (Dmean):",   f"{cerebro.get('minus_gtv_dmean',0):.2f} Gy"),
            ("V10 Gy:",                f"{cerebro.get('v10_cc',0):.2f} cc"),
            ("V12 Gy:",                f"{cerebro.get('v12_cc',0):.2f} cc"),
            ("V14 Gy:",                f"{cerebro.get('v14_cc',0):.2f} cc"),
        ]
        for lbl, val in campos_cerebro:
            y = _line(y, lbl, val)

    y -= 10
    # Índices por PTV
    for ptv_nome, rec in resultados_por_ptv.items():
        params = rec["params"]; resultados = rec["resultados"]
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, f"Índices – {ptv_nome}"); y -= 4
        c.line(40, y, W-40, y); y -= 12

        tv_cc = params.get("tv")
        campos_vol = [
            ("Volume PTV:", f"{params.get('tv',0):.2f} cc"),
            ("Volume TVPIV:", f"{params.get('tvpiv',0):.2f} cc"),
            ("Volume D50 (cc):", f"{params.get('vd50',0):.2f} cc"),
            ("Volume Prescrição:", f"{params.get('piv',0):.2f} cc"),
            ("D98% no PTV:", f"{params.get('dmin98',0):.2f} Gy"),
            ("D2% no PTV:", f"{params.get('dmax2',0):.2f} Gy"),
            ("D50% no PTV:", f"{params.get('d50',0):.2f} Gy"),
            ("Dose Total:", f"{params.get('dptv',0):.2f} Gy"),
        ]
        for lbl, val in campos_vol:
            y = _line(y, lbl, val);
            if y < 80: c.showPage(); _draw_header(); y = H - 95

        y -= 6
        c.setFont("Helvetica-Bold", 10); c.drawString(40, y, "Resultados dos Índices:"); y -= 14

        for key, val in resultados.items():
            cls = classificar_indice(key, val, tv_cc)
            base = _categoria_base(cls)
            label = INDEX_LABELS.get(key, key)
            c.setFont("Helvetica", 9); c.drawString(55, y, f"{label}:  {val:.3f}  →  {cls}")
            # color dot
            rgb = {"EXCELENTE":(0.11,.30,.85),"ACEITÁVEL":(0.08,.5,.24),
                   "SATISFATÓRIO":(0.08,.5,.24),"LIMIAR":(0.7,.35,.04),
                   "INSATISFATÓRIO":(.85,.15,.15),"INACEITÁVEL":(.85,.15,.15)}.get(base,(0.4,0.4,0.4))
            c.setFillColorRGB(*rgb); c.circle(47, y+3, 3, fill=1, stroke=0)
            c.setFillColorRGB(0,0,0)
            y -= 12
            if y < 80: c.showPage(); _draw_header(); y = H - 95

        y -= 8

    # Assinaturas
    if y < 120: c.showPage(); _draw_header(); y = H - 95
    y -= 20
    c.setStrokeColorRGB(.6,.6,.6); c.line(40, y, 200, y); c.line(320, y, 480, y)
    c.setFont("Helvetica", 8); c.drawCentredString(120, y-10, "Médico Radioterapeuta")
    c.drawCentredString(400, y-10, "Físico Médico")

    c.save()
    return buf.getvalue()

# ── DVH chart ─────────────────────────────────────────────────────────────────

_COLOR_PALETTE = [
    "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
    "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf",
    "#aec7e8","#ffbb78","#98df8a","#ff9896","#c5b0d5",
    "#c49c94","#f7b6d2","#c7c7c7","#dbdb8d","#9edae5",
]

def _cor_roi(nome, idx):
    return _COLOR_PALETTE[idx % len(_COLOR_PALETTE)]


def _plot_dvh(dvhs: list, selected_nomes: set, show_percent: bool) -> go.Figure:
    fig = go.Figure()
    color_idx = 0
    for d in dvhs:
        if d["nome"] not in selected_nomes:
            continue
        doses = np.array(d["doses"])
        vols  = np.array(d["vols"])
        units = d["units"]
        vtot  = d["vtotal_cc"]

        if show_percent:
            if units in ("CM3","CC","CM^3") and vtot and vtot > 0:
                y = (vols / vtot) * 100.0
            elif units in ("PERCENT","RELATIVE"):
                y = vols
            else:
                y = vols
            ylabel_unit = "%"
        else:
            if units in ("PERCENT","RELATIVE") and vtot:
                y = vols * vtot / 100.0
            else:
                y = vols
            ylabel_unit = "cm³"

        step = max(1, len(doses)//2000)
        fig.add_trace(go.Scatter(
            x=doses[::step], y=y[::step],
            name=d["nome"], mode="lines",
            line=dict(width=1.6, color=_cor_roi(d["nome"], color_idx)),
            hovertemplate=f"<b>{d['nome']}</b><br>Dose: %{{x:.2f}} Gy<br>Vol: %{{y:.2f}} {ylabel_unit}<extra></extra>"
        ))
        color_idx += 1

    ylabel_unit = "%" if show_percent else "cm³"
    fig.update_layout(
        title=dict(text="DVH Acumulativo", font=dict(size=14, color="#1B3A6B")),
        xaxis_title="Dose (Gy)",
        yaxis_title=f"Volume ({ylabel_unit})",
        height=360,
        margin=dict(l=55, r=180, t=45, b=45),
        legend=dict(orientation="v", x=1.02, xanchor="left", font=dict(size=11)),
        plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
        xaxis=dict(gridcolor="#E2E8F0", zeroline=False),
        yaxis=dict(gridcolor="#E2E8F0", zeroline=False),
    )
    return fig


def _plot_indices(resultados: dict, tv_cc) -> go.Figure:
    nomes  = [INDEX_LABELS.get(k, k) for k in resultados]
    valores = list(resultados.values())
    cores  = [CLS_COLOR.get(_categoria_base(classificar_indice(k, v, tv_cc)), "#64748B")
              for k, v in resultados.items()]

    fig = go.Figure(go.Bar(
        x=valores, y=nomes, orientation="h",
        marker_color=cores, marker_line=dict(width=0.5, color="#9999AA"),
        text=[f"{v:.3f}" for v in valores], textposition="outside", textfont=dict(size=11),
    ))
    xmax = max(valores) * 1.2 if valores else 2
    fig.update_layout(
        height=300, margin=dict(l=10, r=60, t=20, b=30),
        xaxis=dict(range=[0, xmax], gridcolor="#E2E8F0"),
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
    )
    return fig

# ── Session state ─────────────────────────────────────────────────────────────

def _init():
    if "srs" not in st.session_state:
        st.session_state.srs = {
            "paciente":    {"nome":"","id":"","nascimento":"","medico":"","tipo":"Primário"},
            "plano":       {"num_frc":1,"dose_frc":0.0,"dose_total":0.0},
            "cerebro":     {"volume_cc":0.0,"minus_ptv_dmean":0.0,"minus_gtv_dmean":0.0,
                            "v10_cc":0.0,"v12_cc":0.0,"v14_cc":0.0},
            "dvhs":        [],
            "ds_rd":       None, "ds_rs": None, "ds_rtplan": None,
            "ptv_results": {},   # nome -> {params, resultados}
            "current_ptv": None,
            "dvh_select":  set(),
            "dicom_ok":    False,
        }
    if "medicos_srs" not in st.session_state:
        st.session_state.medicos_srs = _carregar_medicos()
    if "hist_df" not in st.session_state:
        st.session_state.hist_df = _carregar_historico()


_init()
s  = st.session_state.srs          # alias

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎯 SRS Analysis")
    st.markdown("---")

    has_results = bool(s["ptv_results"])
    has_dicom   = s["dicom_ok"]

    st.markdown(f"**Status**")
    st.markdown(f"{'🟢' if s['paciente']['nome'] else '⚪'} Dados do paciente")
    st.markdown(f"{'🟢' if has_dicom else '⚪'} DICOM importado")
    st.markdown(f"{'🟢' if s['dvhs'] else '⚪'} DVH carregado ({len(s['dvhs'])} ROIs)")
    st.markdown(f"{'🟢' if has_results else '⚪'} Índices calculados")
    st.markdown("---")

    if has_results:
        st.markdown("**Lesões avaliadas**")
        for nm in s["ptv_results"]:
            n_ok = sum(1 for k,v in s["ptv_results"][nm]["resultados"].items()
                       if _categoria_base(classificar_indice(k,v,s["ptv_results"][nm]["params"].get("tv")))
                          in ("EXCELENTE","ACEITÁVEL","SATISFATÓRIO"))
            total = len(s["ptv_results"][nm]["resultados"])
            emoji = "🟢" if n_ok == total else ("🟡" if n_ok >= total//2 else "🔴")
            st.markdown(f"{emoji} {nm} ({n_ok}/{total})")
        st.markdown("---")

    st.markdown("**Médicos**")
    novo = st.text_input("Adicionar médico", key="novo_medico", label_visibility="collapsed",
                         placeholder="Nome do médico…")
    if st.button("➕ Adicionar", use_container_width=True):
        if novo.strip():
            lista = st.session_state.medicos_srs
            nm_fmt = formatar_nome(novo.strip())
            if nm_fmt not in lista:
                lista.append(nm_fmt)
                lista.sort(key=str.lower)
                _salvar_medicos(lista)
                st.rerun()

    med_sel = st.selectbox("Remover médico", [""] + st.session_state.medicos_srs,
                           key="rem_medico_sel", label_visibility="collapsed")
    if st.button("🗑️ Remover selecionado", use_container_width=True):
        if med_sel and med_sel in st.session_state.medicos_srs:
            st.session_state.medicos_srs.remove(med_sel)
            _salvar_medicos(st.session_state.medicos_srs)
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Limpar sessão", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("srs") or k == "srs":
                del st.session_state[k]
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="srs-header">
  <div class="icon-box">🎯</div>
  <div>
    <h1>SRS Analysis</h1>
    <div class="sub">Avaliação Dosimétrica de Radiocirurgia Estereotáxica · Física Médica</div>
  </div>
</div>
""", unsafe_allow_html=True)
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_aval, tab_stat, tab_painel = st.tabs(["🏥 Avaliação", "📊 Estatística", "📋 Painel"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB AVALIAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

with tab_aval:

    # ── Dados básicos ──────────────────────────────────────────────────────────
    st.markdown('<div class="sec"><h3>Dados do Paciente</h3></div>', unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 3, 2])
    with c1:
        nome_in = st.text_input("Nome Completo", value=s["paciente"]["nome"], key="in_nome")
        s["paciente"]["nome"] = formatar_nome(nome_in) if nome_in.strip() else nome_in
    with c2:
        s["paciente"]["nascimento"] = st.text_input("Data de Nascimento",
            value=s["paciente"]["nascimento"], placeholder="DD/MM/AAAA", key="in_nasc")
    with c3:
        s["paciente"]["id"] = st.text_input("ID do Paciente",
            value=s["paciente"]["id"], key="in_id").upper()
    with c4:
        med_list = st.session_state.medicos_srs or [""]
        med_default = s["paciente"]["medico"] if s["paciente"]["medico"] in med_list else med_list[0]
        s["paciente"]["medico"] = st.selectbox("Médico Radioterapeuta",
            med_list, index=med_list.index(med_default) if med_default in med_list else 0,
            key="in_medico")
    with c5:
        tipos = ["Primário", "Metástase"]
        s["paciente"]["tipo"] = st.selectbox("Tipo de Radiocirurgia",
            tipos, index=tipos.index(s["paciente"]["tipo"]) if s["paciente"]["tipo"] in tipos else 0,
            key="in_tipo")

    # ── Parâmetros do plano ────────────────────────────────────────────────────
    st.markdown('<div class="sec"><h3>Parâmetros do Plano</h3></div>', unsafe_allow_html=True)
    p1, p2, p3 = st.columns(3)
    with p1:
        s["plano"]["num_frc"] = st.number_input("Número de Frações", min_value=1, max_value=30,
            value=max(1, int(s["plano"]["num_frc"] or 1)), step=1, key="in_nfrc")
    with p2:
        s["plano"]["dose_frc"] = st.number_input("Dose por Fração (Gy)", min_value=0.0, max_value=50.0,
            value=float(s["plano"]["dose_frc"] or 0.0), step=0.5, format="%.2f", key="in_dfrc")
    with p3:
        dose_calc = round(s["plano"]["num_frc"] * s["plano"]["dose_frc"], 2)
        if dose_calc > 0 and s["plano"]["dose_total"] != dose_calc:
            s["plano"]["dose_total"] = dose_calc
        s["plano"]["dose_total"] = st.number_input("Dose Total (Gy)", min_value=0.0, max_value=200.0,
            value=float(s["plano"]["dose_total"] or 0.0), step=0.5, format="%.2f", key="in_dtotal")

    # ── Importar DICOM ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec"><h3>Importar Arquivos DICOM</h3></div>', unsafe_allow_html=True)

    if not PYDICOM_OK:
        st.markdown('<div class="warn">⚠️ <b>pydicom</b> não está instalado. '
                    'Execute <code>pip install pydicom</code> para habilitar a importação DICOM.</div>',
                    unsafe_allow_html=True)

    up_col, info_col = st.columns([2, 1])
    with up_col:
        uploaded = st.file_uploader(
            "Selecione 3 arquivos DICOM (RTDOSE, RTSTRUCT, RTPLAN)",
            type=["dcm"], accept_multiple_files=True, key="dicom_upload",
            help="Arraste ou clique para selecionar. Necessário exatamente 1 RTDOSE + 1 RTSTRUCT + 1 RTPLAN.",
        )
        if uploaded and len(uploaded) == 3:
            _parse_key = tuple(sorted((f.name, f.size) for f in uploaded))
            already_parsed = st.session_state.get("_dicom_key") == _parse_key and s["dicom_ok"]

            if already_parsed:
                st.markdown('<div class="ok">✅ DICOM já processado para este conjunto de arquivos.</div>',
                            unsafe_allow_html=True)
            elif st.button("📂 Importar e Processar DICOM", type="primary", use_container_width=True):
                with st.status("Processando arquivos DICOM…", expanded=True) as status:
                    st.write("🔍 Classificando modalidades…")
                    result = _processar_dicom(uploaded)
                    if result:
                        st.write("✅ Arquivos válidos!")
                        st.write("📈 Extraindo DVHs…")
                        s["ds_rd"]    = result["ds_rd"]
                        s["ds_rs"]    = result["ds_rs"]
                        s["ds_rtplan"]= result["ds_rtplan"]
                        s["dvhs"]     = result["dvhs"]
                        s["dvh_select"]= {d["nome"] for d in result["dvhs"]}
                        # Preenche dados do paciente
                        for k,v in result["paciente"].items():
                            if v: s["paciente"][k] = v
                        for k,v in result["plano"].items():
                            if v: s["plano"][k] = v
                        # Adiciona médico à lista se necessário
                        med = result["paciente"].get("medico","")
                        if med and med not in st.session_state.medicos_srs:
                            st.session_state.medicos_srs.append(med)
                            st.session_state.medicos_srs.sort(key=str.lower)
                            _salvar_medicos(st.session_state.medicos_srs)
                        # Autopreenchimento do cérebro
                        st.write("🧠 Preenchendo parâmetros do cérebro…")
                        s["cerebro"] = _autopreencher_cerebro(result["dvhs"])
                        s["dicom_ok"] = True
                        st.session_state["_dicom_key"] = _parse_key
                        status.update(label="DICOM importado com sucesso!", state="complete")
                        st.rerun()
                    else:
                        status.update(label="Falha na importação.", state="error")
        elif uploaded and len(uploaded) != 3:
            st.markdown(f'<div class="warn">⚠️ Selecione exatamente 3 arquivos. '
                        f'Você selecionou {len(uploaded)}.</div>', unsafe_allow_html=True)

    with info_col:
        if s["dicom_ok"]:
            st.markdown(f'<div class="ok">✅ DICOM importado<br>'
                        f'<b>{len(s["dvhs"])}</b> ROIs com DVH</div>', unsafe_allow_html=True)
            st.markdown(f'**Paciente:** {s["paciente"]["nome"]}')
            st.markdown(f'**ID:** {s["paciente"]["id"]}')
        else:
            st.markdown('<div class="info">ℹ️ Importe os arquivos DICOM para '
                        'auto-preencher os campos e visualizar o DVH.</div>', unsafe_allow_html=True)

    # ── DVH ───────────────────────────────────────────────────────────────────
    if s["dvhs"]:
        st.markdown('<div class="sec"><h3>DVH Acumulativo</h3></div>', unsafe_allow_html=True)
        dvh_left, dvh_right = st.columns([1, 3])

        with dvh_left:
            show_pct = st.checkbox("Volume em %", value=True, key="dvh_pct")
            st.markdown("**Estruturas:**")
            todos = st.checkbox("Todas", value=True, key="dvh_all")
            filtro = st.text_input("Filtrar ROIs", placeholder="ex.: PTV, Brain…", key="dvh_filt",
                                   label_visibility="collapsed")
            roi_names = [d["nome"] for d in s["dvhs"] if not filtro or filtro.upper() in d["nome"].upper()]

            if todos:
                s["dvh_select"] = set(roi_names)
            else:
                checked = []
                for nm in roi_names:
                    default = nm in s["dvh_select"]
                    if st.checkbox(nm, value=default, key=f"chk_{nm}"):
                        checked.append(nm)
                s["dvh_select"] = set(checked)

        with dvh_right:
            fig_dvh = _plot_dvh(s["dvhs"], s["dvh_select"], show_pct)
            st.plotly_chart(fig_dvh, use_container_width=True)

    # ── Volumes e parâmetros de dose ───────────────────────────────────────────
    st.markdown('<div class="sec"><h3>Parâmetros Dosimétricos</h3></div>', unsafe_allow_html=True)

    if s["dvhs"] and s["plano"]["dose_total"] > 0:
        # Seletor de PTV quando há DICOM
        candidatos_ptv = [d["nome"] for d in s["dvhs"]
                          if any(k in d["nome"].upper() for k in ("PTV","GTV","CTV"))]
        if not candidatos_ptv:
            candidatos_ptv = [d["nome"] for d in s["dvhs"]]

        st.markdown("**Selecione o(s) alvo(s) para calcular índices:**")
        ptv_sels = st.multiselect("Alvos (PTV/GTV)", candidatos_ptv,
                                   default=candidatos_ptv[:1] if candidatos_ptv else [],
                                   key="ptv_multisel")
        if st.button("⚡ Calcular Índices por Alvo", type="primary", key="btn_calc_dicom"):
            if not ptv_sels:
                st.warning("Selecione ao menos um alvo.")
            else:
                with st.spinner("Calculando…"):
                    s["ptv_results"] = {}
                    erros = []
                    for nm in ptv_sels:
                        dvh_obj = next((d["dvh_obj"] for d in s["dvhs"] if d["nome"] == nm), None)
                        if dvh_obj is None:
                            erros.append(f"DVH de '{nm}' não encontrado.")
                            continue
                        try:
                            rec = _calcular_ptv_indices(dvh_obj, s["ds_rd"], s["ds_rs"], s["plano"]["dose_total"])
                            s["ptv_results"][nm] = rec
                        except Exception as e:
                            erros.append(f"{nm}: {e}")
                    if erros:
                        for e in erros: st.error(e)
                    else:
                        s["current_ptv"] = ptv_sels[0]
                        st.success(f"Índices calculados para {len(s['ptv_results'])} alvo(s).")
                        st.rerun()

    # Campos manuais (sempre visíveis, preenchidos automaticamente ou manualmente)
    current_rec = s["ptv_results"].get(s.get("current_ptv",""), {})
    cur_params  = current_rec.get("params", {})

    if s["ptv_results"]:
        ptv_list = list(s["ptv_results"].keys())
        if len(ptv_list) > 1:
            sel_ptv = st.selectbox("Visualizar lesão/alvo:", ptv_list, key="ptv_view_sel",
                                   index=ptv_list.index(s["current_ptv"]) if s["current_ptv"] in ptv_list else 0)
            if sel_ptv != s["current_ptv"]:
                s["current_ptv"] = sel_ptv
                st.rerun()

    st.markdown("*Preencha manualmente ou importe DICOM para auto-preenchimento:*")
    vm1, vm2, vm3, vm4 = st.columns(4)
    with vm1:
        tv    = st.number_input("Volume PTV (cc)",       min_value=0.0, value=float(cur_params.get("tv",0)    or 0), format="%.3f", key="in_tv")
        tvpiv = st.number_input("Volume TVPIV (cc)",     min_value=0.0, value=float(cur_params.get("tvpiv",0) or 0), format="%.3f", key="in_tvpiv")
    with vm2:
        vd50  = st.number_input("Volume D50% (cc)",      min_value=0.0, value=float(cur_params.get("vd50",0)  or 0), format="%.3f", key="in_vd50")
        piv   = st.number_input("Volume Prescrição (cc)",min_value=0.0, value=float(cur_params.get("piv",0)   or 0), format="%.3f", key="in_piv")
    with vm3:
        dmin98= st.number_input("D98% no PTV (Gy)",      min_value=0.0, value=float(cur_params.get("dmin98",0)or 0), format="%.3f", key="in_dmin98")
        dmax2 = st.number_input("D2% no PTV (Gy)",       min_value=0.0, value=float(cur_params.get("dmax2",0) or 0), format="%.3f", key="in_dmax2")
    with vm4:
        d50   = st.number_input("D50% no PTV (Gy)",      min_value=0.0, value=float(cur_params.get("d50",0)   or 0), format="%.3f", key="in_d50")
        dose_presc_man = st.number_input("Dose Prescrita (Gy)", min_value=0.0,
            value=float(cur_params.get("dptv",0) or s["plano"]["dose_total"] or 0), format="%.2f", key="in_dpresc")

    campos_ok = all([tv > 0, tvpiv > 0, vd50 > 0, piv > 0, dmin98 > 0, dmax2 > 0, d50 > 0, dose_presc_man > 0])

    if not s["dvhs"] and st.button("📐 Calcular Índices (manual)", type="primary",
                                    disabled=not campos_ok, key="btn_calc_manual"):
        params = {"tv":tv,"tvpiv":tvpiv,"vd50":vd50,"piv":piv,
                  "dmin98":dmin98,"dmax2":dmax2,"d50":d50,"dptv":dose_presc_man}
        resultados = AvaliacaoPlanejamentoSRS(**params).analise_completa()
        ptv_nome_manual = s["paciente"]["nome"] or "PTV Manual"
        s["ptv_results"] = {ptv_nome_manual: {"params": params, "resultados": resultados}}
        s["current_ptv"] = ptv_nome_manual
        st.rerun()

    # ── Parâmetros do cérebro ──────────────────────────────────────────────────
    st.markdown('<div class="sec"><h3>Parâmetros – Cérebro</h3></div>', unsafe_allow_html=True)
    cb = s["cerebro"]
    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        cb["volume_cc"]       = st.number_input("Volume do Cérebro (cc)", min_value=0.0,
            value=float(cb.get("volume_cc",0)), format="%.1f", key="cb_vol")
        cb["minus_ptv_dmean"] = st.number_input("Cérebro−PTV Dmean (Gy)", min_value=0.0,
            value=float(cb.get("minus_ptv_dmean",0)), format="%.2f", key="cb_ptv_dmean")
    with bc2:
        cb["minus_gtv_dmean"] = st.number_input("Cérebro−GTV Dmean (Gy)", min_value=0.0,
            value=float(cb.get("minus_gtv_dmean",0)), format="%.2f", key="cb_gtv_dmean")
        cb["v10_cc"]          = st.number_input("V10 Gy (cc)", min_value=0.0,
            value=float(cb.get("v10_cc",0)), format="%.2f", key="cb_v10")
    with bc3:
        cb["v12_cc"]          = st.number_input("V12 Gy (cc)", min_value=0.0,
            value=float(cb.get("v12_cc",0)), format="%.2f", key="cb_v12")
        cb["v14_cc"]          = st.number_input("V14 Gy (cc)", min_value=0.0,
            value=float(cb.get("v14_cc",0)), format="%.2f", key="cb_v14")

    # ── Resultados ─────────────────────────────────────────────────────────────
    if s["ptv_results"]:
        st.markdown('<div class="sec"><h3>Resultados dos Índices</h3></div>', unsafe_allow_html=True)

        res_col, chart_col = st.columns([1, 1])

        ptv_nome = s.get("current_ptv") or list(s["ptv_results"].keys())[0]
        rec = s["ptv_results"].get(ptv_nome, {})
        res = rec.get("resultados", {})
        params = rec.get("params", {})
        tv_cc = params.get("tv")

        with res_col:
            st.markdown(f"**Lesão: {ptv_nome}**")
            rows_html = ""
            for key, val in res.items():
                cls  = classificar_indice(key, val, tv_cc)
                base = _categoria_base(cls)
                css  = CLS_CSS.get(base, "cls-NA")
                rows_html += (
                    f'<div class="result-row">'
                    f'<span class="rname">{INDEX_LABELS.get(key, key)}</span>'
                    f'<span class="rval">{val:.3f}</span>'
                    f'<span class="rcls {css}">{base.title()}</span>'
                    f'</div>'
                )
            st.markdown(rows_html, unsafe_allow_html=True)

        with chart_col:
            if res:
                st.plotly_chart(_plot_indices(res, tv_cc), use_container_width=True)

    # ── Ações ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    a1, a2, a3 = st.columns(3)

    with a1:
        paciente_ok = bool(s["paciente"]["nome"] and s["paciente"]["id"])
        can_save = bool(s["ptv_results"] and paciente_ok)
        if st.button("💾 Salvar no Histórico", type="primary", disabled=not can_save,
                     use_container_width=True, key="btn_save"):
            for ptv_nome, rec in s["ptv_results"].items():
                p = rec["params"]; r = rec["resultados"]
                row = {
                    "Data":     datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Paciente": s["paciente"]["nome"],
                    "ID":       s["paciente"]["id"],
                    "Medico":   s["paciente"]["medico"],
                    "Tipo":     s["paciente"]["tipo"],
                    "Lesao":    ptv_nome,
                    "TV_cc":    round(p.get("tv",0),3),
                    "TVPIV_cc": round(p.get("tvpiv",0),3),
                    "VD50_cc":  round(p.get("vd50",0),3),
                    "PIV_cc":   round(p.get("piv",0),3),
                    "Dmin98_Gy":round(p.get("dmin98",0),3),
                    "Dmax2_Gy": round(p.get("dmax2",0),3),
                    "D50_Gy":   round(p.get("d50",0),3),
                    "DoseTotal_Gy": round(p.get("dptv",0),2),
                    "Brain_cc": round(s["cerebro"].get("volume_cc",0),1),
                    "Brain_V10":round(s["cerebro"].get("v10_cc",0),2),
                    "Brain_V12":round(s["cerebro"].get("v12_cc",0),2),
                    "Brain_V14":round(s["cerebro"].get("v14_cc",0),2),
                    **{k: round(v,4) for k,v in r.items()},
                }
                _salvar_linha_historico(row)
            st.session_state.hist_df = _carregar_historico()
            st.success(f"✅ {len(s['ptv_results'])} lesão(ões) salva(s) no histórico.")

    with a2:
        can_pdf = bool(s["ptv_results"] and paciente_ok)
        if st.button("📄 Gerar Relatório PDF", disabled=not can_pdf,
                     use_container_width=True, key="btn_pdf"):
            if not REPORTLAB_OK:
                st.error("reportlab não instalado.")
            else:
                with st.spinner("Gerando PDF…"):
                    pdf_bytes = _gerar_pdf(
                        paciente=s["paciente"],
                        plano=s["plano"],
                        cerebro=s["cerebro"],
                        resultados_por_ptv=s["ptv_results"],
                    )
                if pdf_bytes:
                    nome_arq = f"SRS_{s['paciente']['nome'].replace(' ','_')}_{date.today()}.pdf"
                    st.download_button("⬇️ Baixar PDF", data=pdf_bytes, file_name=nome_arq,
                                       mime="application/pdf", use_container_width=True)

    with a3:
        if st.button("🗑️ Limpar Campos", use_container_width=True, key="btn_clear"):
            for k in list(st.session_state.keys()):
                if k.startswith(("in_","cb_","dvh_","ptv_","btn_","dicom_")):
                    del st.session_state[k]
            del st.session_state["srs"]
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB ESTATÍSTICA
# ═══════════════════════════════════════════════════════════════════════════════

with tab_stat:
    st.markdown('<div class="sec"><h3>Histórico e Estatísticas</h3></div>', unsafe_allow_html=True)

    s1, s2 = st.columns([1, 4])
    with s1:
        if st.button("🔄 Recarregar", use_container_width=True):
            st.session_state.hist_df = _carregar_historico()

    df = st.session_state.get("hist_df", pd.DataFrame())

    if df.empty:
        st.markdown('<div class="info">ℹ️ Nenhum histórico encontrado. '
                    'Salve avaliações na aba Avaliação para ver estatísticas aqui.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f"**{len(df)} registros** no histórico.")

        # Download CSV
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV completo", data=csv_bytes,
                           file_name="historico_srs.csv", mime="text/csv")

        st.markdown("---")

        # Tabela de dados
        with st.expander("📋 Visualizar todos os registros", expanded=False):
            st.dataframe(df, use_container_width=True, height=300)

        # Estatísticas descritivas
        num_cols = df.select_dtypes(include=["float64","int64","float32"]).columns.tolist()
        if num_cols:
            st.markdown("**Estatísticas Descritivas**")
            stats = df[num_cols].describe().T.round(3)
            st.dataframe(stats, use_container_width=True)

            st.markdown("---")
            # Gráficos
            col_sel = st.selectbox("Selecione a variável para visualizar:", num_cols, key="stat_col")
            if col_sel and col_sel in df.columns:
                hcol, bcol = st.columns(2)
                data_col = df[col_sel].dropna()
                with hcol:
                    fig_h = go.Figure(go.Histogram(x=data_col, nbinsx=20,
                        marker_color="#2563EB", marker_line=dict(color="#1B3A6B",width=0.8)))
                    fig_h.update_layout(
                        title=f"Histograma – {col_sel}", height=300,
                        xaxis_title=col_sel, yaxis_title="Frequência",
                        plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
                        margin=dict(l=40,r=20,t=40,b=40),
                    )
                    st.plotly_chart(fig_h, use_container_width=True)

                with bcol:
                    fig_b = go.Figure(go.Box(y=data_col, name=col_sel,
                        boxpoints="all", jitter=0.3, pointpos=-1.8,
                        marker_color="#2563EB", line_color="#1B3A6B",
                        fillcolor="rgba(37,99,235,0.15)"))
                    fig_b.update_layout(
                        title=f"Boxplot – {col_sel}", height=300,
                        yaxis_title=col_sel,
                        plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
                        margin=dict(l=40,r=20,t=40,b=40),
                    )
                    st.plotly_chart(fig_b, use_container_width=True)

            # Evolução temporal se houver coluna Data
            if "Data" in df.columns and col_sel:
                try:
                    df_t = df[["Data", col_sel]].copy()
                    df_t["Data"] = pd.to_datetime(df_t["Data"])
                    df_t = df_t.dropna().sort_values("Data")
                    fig_t = go.Figure(go.Scatter(x=df_t["Data"], y=df_t[col_sel],
                        mode="lines+markers", line=dict(color="#2563EB"),
                        marker=dict(color="#1B3A6B", size=6)))
                    fig_t.update_layout(
                        title=f"Evolução Temporal – {col_sel}", height=250,
                        xaxis_title="Data", yaxis_title=col_sel,
                        plot_bgcolor="#FAFBFC", paper_bgcolor="#FAFBFC",
                        margin=dict(l=40,r=20,t=40,b=40),
                    )
                    st.plotly_chart(fig_t, use_container_width=True)
                except Exception:
                    pass

# ═══════════════════════════════════════════════════════════════════════════════
# TAB PAINEL
# ═══════════════════════════════════════════════════════════════════════════════

with tab_painel:
    st.markdown('<div class="sec"><h3>Painel da Avaliação Atual</h3></div>', unsafe_allow_html=True)

    if not s["ptv_results"]:
        st.markdown('<div class="info">ℹ️ Nenhuma avaliação calculada. '
                    'Importe DICOM ou preencha os campos na aba Avaliação.</div>',
                    unsafe_allow_html=True)
    else:
        # Cards de resumo
        mc1, mc2, mc3, mc4 = st.columns(4)
        total_indices = sum(len(r["resultados"]) for r in s["ptv_results"].values())
        excelentes = sum(
            sum(1 for k,v in r["resultados"].items()
                if _categoria_base(classificar_indice(k,v,r["params"].get("tv"))) == "EXCELENTE")
            for r in s["ptv_results"].values()
        )
        satisfatorios = sum(
            sum(1 for k,v in r["resultados"].items()
                if _categoria_base(classificar_indice(k,v,r["params"].get("tv")))
                   in ("ACEITÁVEL","SATISFATÓRIO"))
            for r in s["ptv_results"].values()
        )
        insatisfatorios = total_indices - excelentes - satisfatorios

        with mc1:
            st.metric("Lesões Avaliadas", len(s["ptv_results"]))
        with mc2:
            st.metric("Índices Excelentes", excelentes, delta=f"de {total_indices}")
        with mc3:
            st.metric("Aceitáveis/Satisfatórios", satisfatorios)
        with mc4:
            st.metric("⚠️ Insatisfatórios/Inaceitáveis", insatisfatorios,
                      delta_color="inverse" if insatisfatorios > 0 else "normal")

        st.markdown("---")

        # Tabela consolidada de todos os PTVs
        rows = []
        for ptv_nm, rec in s["ptv_results"].items():
            for key, val in rec["resultados"].items():
                cls = classificar_indice(key, val, rec["params"].get("tv"))
                rows.append({
                    "Lesão":    ptv_nm,
                    "Índice":   INDEX_LABELS.get(key, key),
                    "Valor":    round(val, 4) if np.isfinite(val) else None,
                    "Classificação": cls,
                })
        if rows:
            df_res = pd.DataFrame(rows)
            st.dataframe(df_res, use_container_width=True, height=min(400, 40 + 35*len(rows)))

        st.markdown("---")

        # Parâmetros cerebrais
        if any(float(v or 0) > 0 for v in s["cerebro"].values()):
            st.markdown('<div class="sec"><h3>Parâmetros Cerebrais</h3></div>',
                        unsafe_allow_html=True)
            cc1, cc2, cc3 = st.columns(3)
            cb = s["cerebro"]
            with cc1:
                st.metric("Volume Cerebral", f"{cb.get('volume_cc',0):.1f} cc")
                st.metric("V10 Gy", f"{cb.get('v10_cc',0):.2f} cc")
            with cc2:
                st.metric("Cérebro−PTV Dmean", f"{cb.get('minus_ptv_dmean',0):.2f} Gy")
                st.metric("V12 Gy", f"{cb.get('v12_cc',0):.2f} cc")
            with cc3:
                st.metric("Cérebro−GTV Dmean", f"{cb.get('minus_gtv_dmean',0):.2f} Gy")
                st.metric("V14 Gy", f"{cb.get('v14_cc',0):.2f} cc")

        st.markdown("---")
        # Histórico recente
        df_hist = st.session_state.get("hist_df", pd.DataFrame())
        if not df_hist.empty:
            st.markdown('<div class="sec"><h3>Histórico Recente (últimos 10)</h3></div>',
                        unsafe_allow_html=True)
            cols_show = [c for c in ["Data","Paciente","Lesao","CI_RTOG","PCI","Q","CVI","GI"]
                         if c in df_hist.columns]
            st.dataframe(df_hist[cols_show].tail(10), use_container_width=True)
