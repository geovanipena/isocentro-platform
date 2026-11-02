"""
PPR Web – Gerador de Plano de Proteção Radiológica
Versão Streamlit  |  Física Médica / Radioterapia
"""
import streamlit as st
import json, io, re, base64, tempfile, os, hashlib, datetime
from html import escape as _he
from pypdf import PdfReader
import pandas as pd

st.set_page_config(
    page_title="Gerador de PPR",
    page_icon="☢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset / Base ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F1F3D 0%, #1B3A6B 100%);
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] .stMarkdown h1 {
    color: #fff !important;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
[data-testid="stSidebar"] .stMarkdown hr {
    border-color: rgba(255,255,255,0.15);
    margin: 0.5rem 0;
}

/* ── Main area ────────────────────────────────────────────────────────── */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1300px;
}

/* ── Page header ──────────────────────────────────────────────────────── */
.ppr-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 0.25rem;
}
.ppr-header .atom-icon {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #1B3A6B, #2563EB);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(37,99,235,0.35);
}
.ppr-header h1 {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #0F1F3D !important;
    margin: 0 !important;
    line-height: 1.2 !important;
}
.ppr-header .subtitle {
    font-size: 0.8rem;
    color: #64748B;
    font-weight: 400;
    margin-top: 2px;
}

/* ── Progress bar custom ──────────────────────────────────────────────── */
.progress-wrap {
    background: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 0.5rem;
}
.progress-label {
    font-size: 0.78rem;
    color: #64748B;
    font-weight: 500;
    margin-bottom: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.progress-bar-bg {
    background: #E2E8F0;
    border-radius: 99px;
    height: 8px;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.5s ease;
}

/* ── Section header ───────────────────────────────────────────────────── */
.sec-hdr {
    background: linear-gradient(90deg, #EFF6FF 0%, #F8FAFC 100%);
    padding: 8px 14px;
    border-left: 4px solid #2563EB;
    border-radius: 0 8px 8px 0;
    margin: 16px 0 8px 0;
    font-weight: 600;
    color: #1E3A5F;
    font-size: 0.88rem;
    letter-spacing: 0.01em;
}

/* ── Card ─────────────────────────────────────────────────────────────── */
.card {
    background: #fff;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}

/* ── Metric card ──────────────────────────────────────────────────────── */
.metric-card {
    background: #fff;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.metric-card .m-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #0F1F3D;
    line-height: 1;
}
.metric-card .m-label {
    font-size: 0.72rem;
    color: #64748B;
    font-weight: 500;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #F8FAFC;
    border-radius: 10px;
    padding: 4px;
    border: 1px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    font-weight: 500;
    font-size: 0.85rem;
    color: #475569;
    padding: 7px 14px;
    border: none;
    background: transparent;
    transition: all 0.15s ease;
}
.stTabs [aria-selected="true"] {
    background: #1B3A6B !important;
    color: white !important;
    box-shadow: 0 2px 6px rgba(27,58,107,0.3);
}
.stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
    background: #E2E8F0 !important;
    color: #1E3A5F !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 16px;
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #1B3A6B, #2563EB);
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 0.5rem 1.2rem;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3);
    transition: all 0.2s ease;
}
.stButton button[kind="primary"]:hover {
    box-shadow: 0 4px 14px rgba(37,99,235,0.45);
    transform: translateY(-1px);
}
.stButton button[kind="secondary"] {
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    color: #475569;
    font-weight: 500;
    font-size: 0.88rem;
    background: #fff;
    transition: all 0.2s ease;
}
.stButton button[kind="secondary"]:hover {
    border-color: #1B3A6B;
    color: #1B3A6B;
    background: #EFF6FF;
}

/* ── Download button ──────────────────────────────────────────────────── */
.stDownloadButton button {
    background: linear-gradient(135deg, #059669, #10B981) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(16,185,129,0.3) !important;
}

/* ── Expanders ────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #F8FAFC;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    font-weight: 500;
    color: #1E3A5F;
    font-size: 0.88rem;
}
.streamlit-expanderContent {
    border: 1px solid #E2E8F0;
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 12px;
}

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
    border-radius: 8px;
    border: 1px solid #CBD5E1;
    font-size: 0.88rem;
    transition: border-color 0.15s ease;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #2563EB;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}

/* ── Labels ───────────────────────────────────────────────────────────── */
.stTextInput label, .stTextArea label, .stSelectbox label {
    font-size: 0.8rem;
    font-weight: 500;
    color: #374151;
}

/* ── Divider ──────────────────────────────────────────────────────────── */
hr {
    border-color: #E2E8F0;
    margin: 1rem 0;
}

/* ── Info/Success/Error boxes ─────────────────────────────────────────── */
.stAlert {
    border-radius: 10px;
    font-size: 0.85rem;
}

/* ── File uploader ────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #CBD5E1;
    border-radius: 10px;
    padding: 12px;
    background: #F8FAFC;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: #2563EB;
    background: #EFF6FF;
}

/* ── Dataframe / editor ───────────────────────────────────────────────── */
[data-testid="stDataEditor"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #E2E8F0;
}

/* ── Sidebar logo area ────────────────────────────────────────────────── */
.sidebar-logo {
    text-align: center;
    padding: 16px 0 8px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.12);
}
.sidebar-logo .icon {
    font-size: 2.2rem;
    line-height: 1;
    display: block;
}
.sidebar-logo .app-name {
    font-size: 1rem;
    font-weight: 700;
    color: #fff !important;
    letter-spacing: 0.03em;
    margin-top: 6px;
    display: block;
}
.sidebar-logo .app-sub {
    font-size: 0.72rem;
    color: #94A3B8 !important;
    margin-top: 2px;
    display: block;
}

/* ── Badge ────────────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 99px;
    font-size: 0.7rem;
    font-weight: 600;
}
.badge-green { background: #DCFCE7; color: #166534; }
.badge-yellow { background: #FEF9C3; color: #713F12; }
.badge-red { background: #FEE2E2; color: #991B1B; }

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #F1F5F9; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* ── Status chips ─────────────────────────────────────────────────────── */
.chip {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 99px;
    font-size: 0.73rem; font-weight: 600; white-space: nowrap;
}
.chip-ok      { background: #DCFCE7; color: #166534; }
.chip-warn    { background: #FEF9C3; color: #92400E; }
.chip-alert   { background: #FEE2E2; color: #991B1B; }
.chip-expired { background: #7F1D1D; color: #FCA5A5; }
.chip-none    { background: #F1F5F9; color: #94A3B8; }

/* ── Styled table (Vencimentos) ───────────────────────────────────────── */
.venc-wrap {
    border: 1px solid #E2E8F0; border-radius: 10px;
    overflow: hidden; margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.venc-table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
.venc-table th {
    background: #1E3A5F; color: #fff; font-weight: 600;
    padding: 9px 14px; text-align: left;
    font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase;
}
.venc-table th:first-child { border-radius: 8px 0 0 0; }
.venc-table th:last-child  { border-radius: 0 8px 0 0; }
.venc-table td { padding: 8px 14px; border-bottom: 1px solid #F1F5F9; color: #374151; vertical-align: middle; }
.venc-table tr:last-child td { border-bottom: none; }
.venc-table tr:hover td { background: #F8FAFC; }

/* ── Native st.metric ─────────────────────────────────────────────────── */
[data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; font-weight: 500 !important; }

/* ── Sub-tabs (nested) ────────────────────────────────────────────────── */
.stTabs .stTabs [data-baseweb="tab-list"] {
    background: #F1F5F9;
    border: 1px solid #E2E8F0;
}
.stTabs .stTabs [aria-selected="true"] {
    background: #334155 !important;
}

</style>
""", unsafe_allow_html=True)


def sec(txt):
    st.markdown(f'<div class="sec-hdr">{txt}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  DADOS PADRÃO
# ═══════════════════════════════════════════════════════════════════════════════
def dados_padrao() -> dict:
    return {
        "instalacao": {k: "" for k in [
            "nome","matricula_cnen","cnpj","rua","complemento","bairro",
            "cidade","uf","cep","telefone","horario","objetivo",
            "grupo","subgrupo","instituicao","cidade_data","mes","ano",
        ]},
        "responsaveis": [],
        "supervisor":            {"nome":"","rt":"","ra":""},
        "substituto_supervisor": {"nome":"","rt":"","ra":""},
        "responsavel_tecnico":   {"nome":"","crm":"","cb":""},
        "substituto_rt":         {"nome":"","crm":"","cb":""},
        "diretor_clinico":       {"nome":"","crm":"","cb":""},
        "equipes_medicos":[],"equipes_fisicos":[],"equipes_tecnicos":[],
        "equipes_dosimetristas":[],"equipes_enfermagem":[],"equipes_demais":[],
        "asos":[],
        "equipamentos":[],"fontes_referencia":[],"conjunto_dosimetrico":[],
        "instrumentos_medicao":[],"outros_detectores":[],"fantomas":[],
        "monitores_area":[],
        "testes_diarios":[],"testes_mensais":[],"testes_anuais":[],
        "testes_diarios_braqui":[],"testes_trimestrais_braqui":[],
        "testes_mensais_orto":[],
        "sistemas_planejamento":[],"tecnicas_tratamento":[],
        "textos_caps": {k: "" for k in [
            "classificacao_areas","controle_acesso","monitoracao_individual",
            "monitoracao_areas","controle_medico","niveis_operacionais",
            "procedimentos_emergencia","programa_treinamento",
            "programa_educacao","gerencia_rejeitos","calculo_barreiras",
            "matriz_risco","auditoria_externa",
        ]},
        "pdfs": {k: [] for k in [
            "autorizacao_funcionamento","certificados_conjunto_dosimetrico",
            "certificados_monitores_area","certificados_outros",
            "sevrra","auditoria","calculo_blindagem","levantamento_radiometrico",
            "contrato_monitoracao","classificacao_areas","procedimentos_emergencia",
            "gerencia_rejeitos",
        ]},
        "imagens": {"logo":"","classificacao_areas":[],"gerencia_rejeitos":[]},
        "_pdfs_bytes": {},
        "_logo_bytes": None,
        "vencimentos": {k: {"realizacao":"","vencimento":""} for k in [
            "autorizacao_funcionamento","levantamento_radiometrico","auditoria",
            "sevrra","certificados_conjunto_dosimetrico",
            "certificados_outros","certificados_monitores_area",
        ]},
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  IMPORTAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _mesclar_arquivo(base: dict, nome: str, conteudo: dict) -> dict:
    nome_lower = nome.lower().replace(".txt", "").replace(".json", "")

    if nome_lower == "instalacao":
        if "instalacao" in conteudo and isinstance(conteudo["instalacao"], dict):
            base["instalacao"].update(conteudo["instalacao"])
        else:
            base["instalacao"].update(conteudo)

    elif nome_lower == "pessoal":
        chaves_pessoal = [
            "responsaveis", "supervisor", "substituto_supervisor",
            "responsavel_tecnico", "substituto_rt", "diretor_clinico",
            "equipes_medicos", "equipes_fisicos", "equipes_tecnicos",
            "equipes_dosimetristas", "equipes_enfermagem", "equipes_demais", "asos",
        ]
        for k in chaves_pessoal:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "equipamentos":
        chaves_eq = [
            "equipamentos", "fontes_referencia", "conjunto_dosimetrico",
            "instrumentos_medicao", "outros_detectores", "fantomas", "monitores_area",
        ]
        for k in chaves_eq:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "qualidade":
        chaves_gq = [
            "testes_diarios", "testes_mensais", "testes_anuais",
            "testes_diarios_braqui", "testes_trimestrais_braqui",
            "testes_mensais_orto", "sistemas_planejamento", "tecnicas_tratamento",
        ]
        for k in chaves_gq:
            if k in conteudo:
                base[k] = conteudo[k]

    elif nome_lower == "textos":
        if "textos_caps" in conteudo:
            base["textos_caps"].update(conteudo["textos_caps"])
        else:
            base["textos_caps"].update(conteudo)

    elif nome_lower == "pdfs":
        src = conteudo.get("pdfs", conteudo)
        if isinstance(src, dict):
            base["pdfs"].update(src)

    elif nome_lower == "imagens":
        src = conteudo.get("imagens", conteudo)
        if isinstance(src, dict):
            if "logo" in src:
                logo = src["logo"]
                src["logo"] = logo[0] if isinstance(logo, list) and logo else (logo or "")
            base["imagens"].update(src)

    else:
        for k, v in conteudo.items():
            if k.startswith("_"):
                continue
            if k == "instalacao" and isinstance(v, dict):
                base["instalacao"].update(v)
            elif k == "textos_caps" and isinstance(v, dict):
                base["textos_caps"].update(v)
            elif k == "pdfs" and isinstance(v, dict):
                base["pdfs"].update(v)
            elif k == "imagens" and isinstance(v, dict):
                base["imagens"].update(v)
            else:
                base[k] = v

    return base


def importar_jsons(arquivos) -> dict:
    base = dados_padrao()
    for arq in arquivos:
        try:
            conteudo = json.loads(arq.read())
            nome_sem_ext = arq.name.rsplit(".", 1)[0]
            base = _mesclar_arquivo(base, nome_sem_ext, conteudo)
        except Exception as e:
            st.warning(f"⚠️ Erro ao ler **{arq.name}**: {e}")
    return base


def _hash_dados(dados: dict) -> str:
    exportar = {k: v for k, v in dados.items() if not k.startswith("_")}
    return hashlib.md5(json.dumps(exportar, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# ── Session state ─────────────────────────────────────────────────────────────
if "dados" not in st.session_state:
    st.session_state.dados = dados_padrao()
if "sv" not in st.session_state:
    st.session_state.sv = 0
if "hash_salvo" not in st.session_state:
    st.session_state.hash_salvo = _hash_dados(st.session_state.dados)
if "onboarding_done" not in st.session_state:
    st.session_state.onboarding_done = False
if "ultima_exportacao" not in st.session_state:
    st.session_state.ultima_exportacao = ""

d = st.session_state.dados
sv = st.session_state.sv


# ═══════════════════════════════════════════════════════════════════════════════
#  FUNÇÕES DE PROGRESSO E VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def calcular_progresso(dados: dict) -> tuple:
    inst = dados.get("instalacao", {})
    itens = [
        {"label": "Nome da instalação",          "ok": bool(inst.get("nome")),           "critico": True},
        {"label": "Matrícula CNEN",              "ok": bool(inst.get("matricula_cnen")), "critico": True},
        {"label": "CNPJ",                        "ok": bool(inst.get("cnpj")),           "critico": True},
        {"label": "Endereço completo",           "ok": all(inst.get(k) for k in ["rua","cidade","uf","cep"]), "critico": False},
        {"label": "Grupo/Subgrupo CNEN",         "ok": bool(inst.get("grupo")),          "critico": True},
        {"label": "Objetivo da instalação",      "ok": bool(inst.get("objetivo")),       "critico": False},
        {"label": "Titular(es) cadastrado(s)",   "ok": len(dados.get("responsaveis",[])) > 0, "critico": True},
        {"label": "SPR (nome + RT + RA)",        "ok": all(dados.get("supervisor",{}).get(k) for k in ["nome","rt","ra"]), "critico": True},
        {"label": "Substituto do SPR",           "ok": bool(dados.get("substituto_supervisor",{}).get("nome")), "critico": True},
        {"label": "Responsável Técnico",         "ok": all(dados.get("responsavel_tecnico",{}).get(k) for k in ["nome","crm"]), "critico": True},
        {"label": "Substituto do RT",            "ok": bool(dados.get("substituto_rt",{}).get("nome")), "critico": False},
        {"label": "Médicos cadastrados",         "ok": len(dados.get("equipes_medicos",[])) > 0,   "critico": True},
        {"label": "Físicos médicos",             "ok": len(dados.get("equipes_fisicos",[])) > 0,   "critico": True},
        {"label": "Técnicos em RT",              "ok": len(dados.get("equipes_tecnicos",[])) > 0,  "critico": False},
        {"label": "Equipamentos/Fontes",         "ok": len(dados.get("equipamentos",[])) > 0,      "critico": True},
        {"label": "Conjuntos dosimétricos",      "ok": len(dados.get("conjunto_dosimetrico",[])) > 0, "critico": True},
        {"label": "Monitores de área",           "ok": len(dados.get("monitores_area",[])) > 0,    "critico": False},
        {"label": "Testes diários definidos",    "ok": len(dados.get("testes_diarios",[])) > 0,    "critico": True},
        {"label": "Testes mensais definidos",    "ok": len(dados.get("testes_mensais",[])) > 0,    "critico": True},
        {"label": "Testes anuais definidos",     "ok": len(dados.get("testes_anuais",[])) > 0,     "critico": True},
        {"label": "Sistemas de planejamento",    "ok": len(dados.get("sistemas_planejamento",[])) > 0, "critico": False},
        {"label": "Texto: Classificação de áreas",      "ok": bool(dados.get("textos_caps",{}).get("classificacao_areas")),    "critico": True},
        {"label": "Texto: Monitoração individual",      "ok": bool(dados.get("textos_caps",{}).get("monitoracao_individual")), "critico": True},
        {"label": "Texto: Procedimentos de emergência", "ok": bool(dados.get("textos_caps",{}).get("procedimentos_emergencia")),"critico": True},
        {"label": "Texto: Gerência de rejeitos",        "ok": bool(dados.get("textos_caps",{}).get("gerencia_rejeitos")),     "critico": False},
        {"label": "Texto: Cálculo de barreiras",        "ok": bool(dados.get("textos_caps",{}).get("calculo_barreiras")),    "critico": False},
    ]
    total = len(itens)
    ok_count = sum(1 for i in itens if i["ok"])
    return int(ok_count / total * 100), itens


def erros_criticos(itens: list) -> list:
    return [i for i in itens if i["critico"] and not i["ok"]]


def _status_tab(subset: list) -> str:
    """🟢 tudo ok · 🔴 crítico faltando · 🟡 apenas opcionais faltando."""
    if all(i["ok"] for i in subset):
        return "🟢"
    if any(not i["ok"] and i["critico"] for i in subset):
        return "🔴"
    return "🟡"


def avisos_tab(checks: list[dict]):
    """Mostra banner de aviso com campos não preenchidos para a aba atual."""
    pendentes = [c for c in checks if not c["ok"]]
    if not pendentes:
        return
    criticos_tab  = [c for c in pendentes if c["critico"]]
    opcionais_tab = [c for c in pendentes if not c["critico"]]
    linhas = []
    for c in criticos_tab:
        linhas.append(f"<li>❌ <b>{c['label']}</b> <span style='color:#991B1B;font-size:0.75rem;'>(obrigatório)</span></li>")
    for c in opcionais_tab:
        linhas.append(f"<li>⚠️ {c['label']}</li>")
    cor_borda = "#EF4444" if criticos_tab else "#F59E0B"
    cor_bg    = "#FEF2F2" if criticos_tab else "#FFFBEB"
    cor_txt   = "#7F1D1D" if criticos_tab else "#78350F"
    st.markdown(f"""
    <div style="background:{cor_bg}; border:1px solid {cor_borda}; border-left:4px solid {cor_borda};
         border-radius:8px; padding:10px 14px; margin-bottom:12px;">
        <div style="font-weight:600; color:{cor_txt}; font-size:0.85rem; margin-bottom:6px;">
            {'❌ Campos obrigatórios faltando' if criticos_tab else '⚠️ Campos não preenchidos'}
            &nbsp;<span style="font-weight:400; font-size:0.8rem;">({len(pendentes)} item{'s' if len(pendentes)>1 else ''})</span>
        </div>
        <ul style="margin:0; padding-left:18px; color:{cor_txt}; font-size:0.82rem; line-height:1.8;">
            {''.join(linhas)}
        </ul>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS PARA TABELAS
# ═══════════════════════════════════════════════════════════════════════════════

def tabela_editavel(chave: str, colunas: list, altura: int = None, sort_by: str = None) -> list:
    col_cfg = {c[0]: st.column_config.TextColumn(c[1]) for c in colunas}
    df_ini = pd.DataFrame(d.get(chave, []) or [], columns=[c[0] for c in colunas])
    for c in colunas:
        if c[0] not in df_ini.columns:
            df_ini[c[0]] = ""
    df_ini = df_ini[[c[0] for c in colunas]]
    # Garante dtype string em todas as colunas (NaN de colunas novas causaria TypeError no TextColumn)
    df_ini = df_ini.fillna("").astype(str).replace({"nan": "", "None": ""})
    if sort_by and sort_by in df_ini.columns:
        df_ini = df_ini.sort_values(sort_by, key=lambda s: s.str.lower()).reset_index(drop=True)

    # Altura dinâmica: mostra todas as linhas sem rolagem (38px/linha + 45px header/footer)
    _n = max(len(df_ini), 1)
    _h = altura if altura else max(80, 45 + 38 * (_n + 1))

    df_edit = st.data_editor(
        df_ini,
        column_config=col_cfg,
        num_rows="dynamic",
        use_container_width=True,
        height=_h,
        key=f"editor_{chave}_{sv}",
    )
    rows = df_edit.to_dict("records")
    rows = [r for r in rows if any(str(v).strip() for v in r.values())]
    # Normalize stored rows to strings for comparison so int/float values from
    # imported JSON don't cause a spurious write (and hash change) every render.
    stored = [
        {k: str(v) if v is not None else "" for k, v in r.items()}
        for r in (d.get(chave) or [])
    ]
    if rows != stored:
        d[chave] = rows
    return rows


def bloco_resp(titulo: str, chave: str, campos: list):
    st.markdown(
        f"<div style='background:#F8FAFC; border:1px solid #E2E8F0; "
        f"border-left:3px solid #2563EB; border-radius:0 8px 8px 0; "
        f"padding:7px 12px; margin-bottom:8px; "
        f"font-size:0.83rem; font-weight:600; color:#1E3A5F;'>"
        f"👤 {titulo}</div>",
        unsafe_allow_html=True,
    )
    val = d.get(chave, {})
    cols = st.columns(len(campos))
    for i, (k, lbl) in enumerate(campos):
        val[k] = cols[i].text_input(lbl, val.get(k, ""), key=f"{chave}_{k}_{sv}")
    d[chave] = val
    st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  UPLOAD DE PDFs
# ═══════════════════════════════════════════════════════════════════════════════

def upload_pdfs(chave_pdfs: str, label: str, tipos: list = None):
    if tipos is None:
        tipos = ["pdf"]
    # key inclui os tipos aceitos para evitar conflito de estado de sessão
    _tipo_key = "_".join(sorted(tipos))
    uploaded = st.file_uploader(
        label, type=tipos, accept_multiple_files=True,
        key=f"up_{chave_pdfs}_{_tipo_key}"
    )
    if uploaded:
        if "_pdfs_bytes" not in d:
            d["_pdfs_bytes"] = {}
        _max_bytes = 20 * 1024 * 1024
        _carregados = 0
        for f in uploaded:
            if f.size > _max_bytes:
                st.warning(f"⚠️ **{f.name}** excede 20 MB — ignorado.")
                continue
            b64 = base64.b64encode(f.read()).decode()
            key = f"{chave_pdfs}__{f.name}"
            d["_pdfs_bytes"][key] = {"nome": f.name, "data": b64, "chave_secao": chave_pdfs}
            _carregados += 1
        if _carregados:
            st.success(f"✅ {_carregados} arquivo(s) carregado(s)")

    if d.get("_pdfs_bytes"):
        arqs = [v["nome"] for k, v in d["_pdfs_bytes"].items()
                if v.get("chave_secao") == chave_pdfs]
        if arqs:
            st.caption("Arquivos carregados: " + " · ".join(arqs))


def extrair_asos_do_pdf(pdf_bytes: bytes) -> list[dict]:
    """Extrai registros de ASO de um PDF usando pypdf + Claude."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texto = "\n".join(page.extract_text() or "" for page in reader.pages)

    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não encontrada. Configure em Settings > Secrets no Streamlit Cloud."
        )
    client = _get_anthropic_client(api_key)
    msg = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": (
                "Analise o texto abaixo extraído de um arquivo PDF contendo Atestados de Saúde "
                "Ocupacional (ASO) de profissionais de saúde. Para cada profissional encontrado, "
                "retorne uma lista JSON com objetos contendo:\n"
                '  - "nome": nome completo do profissional\n'
                '  - "ultimo": data do último ASO no formato DD/MM/AAAA\n'
                '  - "validade": data de validade do ASO no formato DD/MM/AAAA\n\n'
                "Retorne APENAS o JSON, sem texto adicional. Exemplo:\n"
                '[{"nome": "João Silva", "ultimo": "10/01/2024", "validade": "10/01/2025"}]\n\n'
                f"TEXTO DO PDF:\n{texto[:12000]}"
            )
        }]
    )
    if not msg.content or not hasattr(msg.content[0], "text"):
        raise ValueError("A IA não retornou conteúdo de texto.")
    raw = msg.content[0].text.strip()
    # Extrai JSON mesmo se houver texto extra ao redor
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    else:
        raise ValueError("A IA não retornou uma lista JSON válida.")
    registros = json.loads(raw)
    return [
        {
            "nome":      str(r.get("nome", "")).strip(),
            "ultimo":    str(r.get("ultimo", "")).strip(),
            "validade":  str(r.get("validade", "")).strip(),
        }
        for r in registros if isinstance(r, dict)
    ]



def extrair_vencimentos_dos_pdfs(pdfs_bytes_map: dict) -> dict:
    """Extrai datas de realização e vencimento de cada PDF carregado usando Claude."""
    _chaves_nome = {
        "autorizacao_funcionamento":         "Autorização de Funcionamento",
        "levantamento_radiometrico":         "Levantamento Radiométrico",
        "auditoria":                         "Auditoria Dosimétrica",
        "sevrra":                            "SEVRRA",
        "certificados_conjunto_dosimetrico": "Certificados de Conjuntos Dosimétricos",
        "certificados_outros":               "Certificados Outros",
        "certificados_monitores_area":       "Certificados de Monitores de Área",
    }
    textos_por_secao: dict = {}
    for info in pdfs_bytes_map.values():
        sec_k = info.get("chave_secao", "")
        if sec_k not in _chaves_nome:
            continue
        try:
            pdf_bytes = base64.b64decode(info["data"])
            reader = PdfReader(io.BytesIO(pdf_bytes))
            texto = "\n".join(p.extract_text() or "" for p in reader.pages)
            textos_por_secao.setdefault(sec_k, []).append(texto[:3000])
        except Exception:
            pass

    if not textos_por_secao:
        return {}

    api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada.")
    client = _get_anthropic_client(api_key)

    resultado: dict = {}
    for sec_k, textos in textos_por_secao.items():
        nome_doc = _chaves_nome[sec_k]
        texto_comb = "\n\n---\n\n".join(textos)[:5000]
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=256,
            messages=[{"role": "user", "content": (
                f"Analise o texto de um documento '{nome_doc}'. "
                "Extraia a data de realização/emissão e a data de vencimento/validade. "
                'Responda APENAS com JSON: {"realizacao":"DD/MM/AAAA","vencimento":"DD/MM/AAAA"}. '
                "Se não encontrar, use string vazia.\n\n"
                f"Texto:\n{texto_comb}"
            )}],
        )
        if not msg.content or not hasattr(msg.content[0], "text"):
            continue
        raw = msg.content[0].text.strip()
        m = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if m:
            try:
                resultado[sec_k] = json.loads(m.group())
            except Exception:
                pass
    return resultado


# ── Helpers de módulo ────────────────────────────────────────────────────────

_MESES_PT = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]


def _parse_br(s: str):
    import re as _re2
    m = _re2.match(r"(\d{2})/(\d{2})/(\d{4})", str(s or "").strip())
    return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def _pdf_ok(chave: str, pdfs_bytes: dict, pdfs_importados: dict) -> bool:
    return (any(v.get("chave_secao") == chave for v in pdfs_bytes.values()) or
            bool([p for p in pdfs_importados.get(chave, []) if p]))


@st.cache_resource
def _get_anthropic_client(api_key: str):
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

pct_prog, itens_prog = calcular_progresso(d)
hash_atual = _hash_dados(d)
dados_modificados = hash_atual != st.session_state.hash_salvo

with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="icon">☢️</span>
        <span class="app-name">Gerador de PPR</span>
        <span class="app-sub">Física Médica / Radioterapia</span>
    </div>
    """, unsafe_allow_html=True)

    nome_inst = d["instalacao"].get("nome") or "Nova Instalação"
    st.markdown(f"**{nome_inst}**")
    st.caption(f"CNEN: {d['instalacao'].get('matricula_cnen') or '—'}")

    st.markdown("---")

    # Progress ring summary
    cor_prog = "#22C55E" if pct_prog >= 80 else "#F59E0B" if pct_prog >= 50 else "#EF4444"
    st.markdown(f"""
    <div style="text-align:center; padding:8px 0;">
        <div style="font-size:2.2rem; font-weight:800; color:{cor_prog}; line-height:1;">{pct_prog}%</div>
        <div style="font-size:0.72rem; color:#94A3B8; margin-top:4px; letter-spacing:0.05em; text-transform:uppercase;">Preenchimento</div>
        <div style="background:rgba(255,255,255,0.15); border-radius:99px; height:5px; margin:8px 0; overflow:hidden;">
            <div style="width:{pct_prog}%; background:{cor_prog}; height:100%; border-radius:99px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Progresso por aba ─────────────────────────────────────────────────────
    _itens = itens_prog  # já calculado acima
    _pdfs_imp_sb = d.get("pdfs", {})
    _pdfs_up_sb  = d.get("_pdfs_bytes", {})
    _b_pdf = "🟢" if all(_pdf_ok(s, _pdfs_up_sb, _pdfs_imp_sb) for s in ["autorizacao_funcionamento","calculo_blindagem","sevrra"]) else "🔴"
    _tabs_sb = [
        (_status_tab(_itens[0:6]),   "Instalação"),
        (_status_tab(_itens[6:14]),  "Pessoal"),
        (_status_tab(_itens[14:17]), "Equipamentos"),
        (_status_tab(_itens[17:21]), "Garantia Qualidade"),
        (_status_tab(_itens[21:]),   "Textos"),
        (_b_pdf,                     "Arquivos PDFs"),
    ]
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'padding:4px 8px;margin-bottom:2px;border-radius:6px;font-size:0.75rem;'
        f'color:#CBD5E1;background:rgba(255,255,255,0.05);">'
        f'<span>{label}</span><span style="font-size:0.9rem;">{icon}</span></div>'
        for icon, label in _tabs_sb
    )
    st.markdown(f'<div style="padding:4px 0 8px;">{rows}</div>', unsafe_allow_html=True)

    if dados_modificados:
        st.markdown("""
        <div style="background:rgba(250,204,21,0.15); border:1px solid rgba(250,204,21,0.4);
             border-radius:8px; padding:7px 10px; font-size:0.75rem; color:#FCD34D; text-align:center;">
            ⚠️ Dados não salvos
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    # Export — dict comprehension evita deepcopy de MBs de base64
    exportar_d = {k: v for k, v in d.items() if not k.startswith("_")}
    json_str = json.dumps(exportar_d, ensure_ascii=False, indent=2)
    _nome_inst = (d["instalacao"].get("nome") or "PPR").replace(" ", "_")
    _data_hoje = datetime.date.today().strftime("%d-%m-%Y")
    nome_arq   = f"PPR_{_nome_inst}_{_data_hoje}"
    _btn_label = "💾 Salvar projeto" if not dados_modificados else "💾 Salvar projeto ⚠️"
    if st.download_button(
        _btn_label,
        data=json_str.encode("utf-8"),
        file_name=f"{nome_arq}.json",
        mime="application/json",
        use_container_width=True,
        type="primary" if dados_modificados else "secondary",
    ):
        from datetime import datetime as _dt_cls
        st.session_state.hash_salvo = hash_atual
        st.session_state.ultima_exportacao = _dt_cls.now().strftime("%H:%M")
    if st.session_state.ultima_exportacao:
        st.caption(f"Última exportação: {st.session_state.ultima_exportacao}")

    st.markdown("---")

    # Quick stats
    n_ok = sum(1 for i in itens_prog if i["ok"])
    n_criticos = len(erros_criticos(itens_prog))
    st.markdown(f"""
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:6px; padding:4px 0;">
        <div style="background:rgba(34,197,94,0.15); border-radius:8px; padding:8px; text-align:center;">
            <div style="font-size:1.3rem; font-weight:700; color:#4ADE80;">{n_ok}</div>
            <div style="font-size:0.65rem; color:#86EFAC; text-transform:uppercase; letter-spacing:0.04em;">Completos</div>
        </div>
        <div style="background:rgba(239,68,68,0.15); border-radius:8px; padding:8px; text-align:center;">
            <div style="font-size:1.3rem; font-weight:700; color:#F87171;">{n_criticos}</div>
            <div style="font-size:0.65rem; color:#FCA5A5; text-transform:uppercase; letter-spacing:0.04em;">Pendentes</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  HEADER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="ppr-header">
    <div class="atom-icon">☢️</div>
    <div>
        <h1>Plano de Proteção Radiológica</h1>
        <div class="subtitle">{nome_inst} &nbsp;·&nbsp; Física Médica / Radioterapia</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Progress bar
cor_bar = "#22C55E" if pct_prog >= 80 else "#F59E0B" if pct_prog >= 50 else "#EF4444"
st.markdown(f"""
<div class="progress-wrap">
    <div class="progress-label">
        <span>Preenchimento do formulário</span>
        <span style="font-weight:700; color:{cor_bar};">{pct_prog}% concluído</span>
    </div>
    <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{pct_prog}%; background:{cor_bar};"></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── Onboarding ────────────────────────────────────────────────────────────────
if not st.session_state.onboarding_done and not d["instalacao"].get("nome"):
    st.markdown("""
    <div style="max-width:600px; margin:32px auto; text-align:center;">
        <div style="font-size:3rem; margin-bottom:12px;">☢️</div>
        <h2 style="font-size:1.6rem; font-weight:800; color:#1E3A5F; margin-bottom:6px;">
            Bem-vindo ao Gerador de PPR
        </h2>
        <p style="color:#64748B; font-size:0.95rem; margin-bottom:32px;">
            Plano de Proteção Radiológica · Física Médica / Radioterapia
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_novo, col_carregar = st.columns(2, gap="large")
    with col_novo:
        st.markdown("""
        <div style="background:#F0F9FF; border:2px solid #BAE6FD; border-radius:16px;
                    padding:28px 24px; text-align:center; min-height:160px;">
            <div style="font-size:2.2rem;">🆕</div>
            <div style="font-weight:700; font-size:1.05rem; color:#0C4A6E; margin:10px 0 6px;">
                Novo Projeto
            </div>
            <div style="font-size:0.82rem; color:#0369A1;">
                Preencha os dados a partir do zero
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Começar projeto novo", use_container_width=True, type="primary"):
            st.session_state.sv += 1
            st.session_state.onboarding_done = True
            st.rerun()

    with col_carregar:
        st.markdown("""
        <div style="background:#F0FDF4; border:2px solid #BBF7D0; border-radius:16px;
                    padding:28px 24px; text-align:center; min-height:160px;">
            <div style="font-size:2.2rem;">📂</div>
            <div style="font-weight:700; font-size:1.05rem; color:#14532D; margin:10px 0 6px;">
                Carregar Projeto
            </div>
            <div style="font-size:0.82rem; color:#15803D;">
                Importe um JSON ou TXT salvo anteriormente
            </div>
        </div>
        """, unsafe_allow_html=True)
        arqs_ob = st.file_uploader(
            "Selecionar arquivo(s)",
            type=["json", "txt"],
            accept_multiple_files=True,
            key="import_json_onboarding",
            help="1 arquivo unificado (novo formato) OU arquivos separados do formato antigo.",
        )
        if arqs_ob:
            try:
                novo = importar_jsons(arqs_ob)
                novo["_pdfs_bytes"] = {}
                novo["_logo_bytes"] = None
                for k in ("dados", "hash_salvo", "onboarding_done",
                          "ultima_exportacao", "_pdf_gerado"):
                    st.session_state.pop(k, None)
                st.session_state.dados = novo
                st.session_state.sv += 1
                st.session_state.hash_salvo = _hash_dados(novo)
                st.session_state.onboarding_done = True
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao importar: {e}")

    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  TABS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
# Badges por aba (reutiliza itens_prog já calculado)
_pdfs_imp_tb = d.get("pdfs", {})
_pdfs_up_tb  = d.get("_pdfs_bytes", {})
_b = [
    _status_tab(itens_prog[0:6]),
    _status_tab(itens_prog[6:14]),
    _status_tab(itens_prog[14:17]),
    _status_tab(itens_prog[17:21]),
    _status_tab(itens_prog[21:]),
    "🟢" if all(_pdf_ok(s, _pdfs_up_tb, _pdfs_imp_tb) for s in ["autorizacao_funcionamento","calculo_blindagem","sevrra"]) else "🔴",
]
tabs = st.tabs([
    f"🏥 Instalação {_b[0]}",
    f"👥 Pessoal {_b[1]}",
    f"⚙️ Equipamentos {_b[2]}",
    f"✅ Garantia da Qualidade {_b[3]}",
    f"📝 Textos {_b[4]}",
    f"🗂️ Arquivos {_b[5]}",
    "📅 Vencimentos",
    "📑 Gerar PDF",
])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 1 – INSTALAÇÃO
# ───────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    inst = d["instalacao"]
    avisos_tab([
        {"label": "Nome da instalação",  "ok": bool(inst.get("nome")),           "critico": True},
        {"label": "Matrícula CNEN",      "ok": bool(inst.get("matricula_cnen")), "critico": True},
        {"label": "CNPJ",               "ok": bool(inst.get("cnpj")),           "critico": True},
        {"label": "Endereço completo",  "ok": all(inst.get(k) for k in ["rua","cidade","uf","cep"]), "critico": False},
        {"label": "Grupo CNEN",         "ok": bool(inst.get("grupo")),          "critico": True},
        {"label": "Objetivo",           "ok": bool(inst.get("objetivo")),       "critico": False},
    ])
    sec("Identificação da Instituição")
    c1, c2 = st.columns([1, 1])
    with c1:
        inst["nome"]           = st.text_input("Nome da Instituição *", inst.get("nome",""), key=f"inst_nome_{sv}")
        inst["matricula_cnen"] = st.text_input("Matrícula CNEN *", inst.get("matricula_cnen",""), key=f"inst_matricula_cnen_{sv}")
        inst["cnpj"]           = st.text_input("CNPJ *", inst.get("cnpj",""), key=f"inst_cnpj_{sv}")
        inst["objetivo"]       = st.text_area("Objetivo", inst.get("objetivo",""), key=f"inst_objetivo_{sv}", height=90)
        inst["horario"]        = st.text_input("Horário de Funcionamento", inst.get("horario",""), key=f"inst_horario_{sv}")
        inst["telefone"]       = st.text_input("Telefone", inst.get("telefone",""), key=f"inst_telefone_{sv}")
    with c2:
        inst["rua"]       = st.text_input("Rua / Av. *", inst.get("rua",""), key=f"inst_rua_{sv}")
        a, b = st.columns([1, 2])
        inst["complemento"] = a.text_input("Número", inst.get("complemento",""), key=f"inst_comp_{sv}")
        inst["bairro"]      = b.text_input("Bairro", inst.get("bairro",""), key=f"inst_bairro_{sv}")
        a, b, c3 = st.columns([3, 1, 2])
        inst["cidade"] = a.text_input("Cidade *", inst.get("cidade",""), key=f"inst_cidade_{sv}")
        inst["uf"]     = b.text_input("UF *", inst.get("uf",""), key=f"inst_uf_{sv}")
        inst["cep"]    = c3.text_input("CEP *", inst.get("cep",""), key=f"inst_cep_{sv}")
        a, b = st.columns(2)
        inst["grupo"]    = a.text_input("Grupo CNEN *", inst.get("grupo",""), key=f"inst_grupo_{sv}")
        inst["subgrupo"] = b.text_input("Subgrupo", inst.get("subgrupo",""), key=f"inst_subgrupo_{sv}")
        inst["instituicao"] = st.text_input("Cabeçalho (instituição)", inst.get("instituicao",""), key=f"inst_instituicao_{sv}")

    # Preenche cidade/mês/ano automaticamente apenas se ainda não definidos
    _hoje = datetime.date.today()
    if not inst.get("cidade_data"):
        inst["cidade_data"] = inst.get("cidade") or ""
    if not inst.get("mes"):
        inst["mes"] = _MESES_PT[_hoje.month - 1]
    if not inst.get("ano"):
        inst["ano"] = str(_hoje.year)


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 2 – PESSOAL
# ───────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    avisos_tab([
        {"label": "Titular(es) cadastrado(s)",  "ok": len(d.get("responsaveis",[])) > 0, "critico": True},
        {"label": "SPR – Nome",                 "ok": bool(d.get("supervisor",{}).get("nome")), "critico": True},
        {"label": "SPR – RT e RA",              "ok": bool(d.get("supervisor",{}).get("rt")) and bool(d.get("supervisor",{}).get("ra")), "critico": True},
        {"label": "Substituto do SPR",          "ok": bool(d.get("substituto_supervisor",{}).get("nome")), "critico": True},
        {"label": "Responsável Técnico",        "ok": all(d.get("responsavel_tecnico",{}).get(k) for k in ["nome","crm"]), "critico": True},
        {"label": "Substituto do RT",           "ok": bool(d.get("substituto_rt",{}).get("nome")), "critico": False},
        {"label": "Diretor Clínico",            "ok": bool(d.get("diretor_clinico",{}).get("nome")), "critico": False},
        {"label": "Médicos cadastrados",        "ok": len(d.get("equipes_medicos",[])) > 0, "critico": True},
        {"label": "Físicos médicos",            "ok": len(d.get("equipes_fisicos",[])) > 0, "critico": True},
        {"label": "Técnicos em RT",             "ok": len(d.get("equipes_tecnicos",[])) > 0, "critico": False},
        {"label": "ASOs preenchidos",           "ok": len(d.get("asos",[])) > 0, "critico": False},
    ])
    sub = st.tabs(["👤 Responsáveis", "👨‍⚕️ Médicos", "🔬 Físicos",
                   "🛠️ Técnicos", "📐 Dosimetristas", "🩺 Enfermagem",
                   "👥 Demais IOEs", "🏥 ASOs"])

    with sub[0]:
        sec("Titulares da Instalação")
        tabela_editavel("responsaveis",
            [("nome","Nome"),("cpf","CPF"),("cargo","Cargo")], altura=180, sort_by="nome")

        sec("Supervisor de Radioproteção (SPR)")
        bloco_resp("SPR", "supervisor",
            [("nome","Nome"),("rt","CNEN RT"),("ra","CNEN RA")])
        bloco_resp("Substituto do SPR", "substituto_supervisor",
            [("nome","Nome"),("rt","CNEN RT"),("ra","CNEN RA")])

        sec("Responsável Técnico (RT)")
        bloco_resp("RT Titular", "responsavel_tecnico",
            [("nome","Nome"),("crm","CRM"),("cb","CB")])
        bloco_resp("Substituto do RT", "substituto_rt",
            [("nome","Nome"),("crm","CRM"),("cb","CB")])

        sec("Diretor Clínico")
        bloco_resp("Diretor Clínico", "diretor_clinico",
            [("nome","Nome"),("crm","CRM")])

    with sub[1]:
        sec("Equipe de Radio-Oncologistas")
        tabela_editavel("equipes_medicos",
            [("nome","Nome"),("crm","CRM"),("cb","CB"),("venc_cb","Venc. CB"),("carga","Carga")], sort_by="nome")

    with sub[2]:
        sec("Equipe de Físicos Médicos")
        tabela_editavel("equipes_fisicos",
            [("nome","Nome"),("rt","RT"),("venc_rt","Venc. RT"),("ra","RA"),("venc_ra","Venc. RA"),("formacao","Formação"),("carga","Carga")], sort_by="nome")

    with sub[3]:
        sec("Equipe de Técnicos em Radioterapia")
        tabela_editavel("equipes_tecnicos",
            [("nome","Nome"),("crtr","CRTR"),("carga","Carga")], sort_by="nome")

    with sub[4]:
        sec("Equipe de Dosimetristas")
        tabela_editavel("equipes_dosimetristas",
            [("nome","Nome"),("registro","Registro"),("carga","Carga")], sort_by="nome")

    with sub[5]:
        sec("Equipe de Enfermagem")
        tabela_editavel("equipes_enfermagem",
            [("nome","Nome"),("coren","COREN"),("carga","Carga")], sort_by="nome")

    with sub[6]:
        sec("Demais IOEs")
        tabela_editavel("equipes_demais",
            [("nome","Nome"),("cargo","Cargo"),("carga","Carga")], sort_by="nome")

    with sub[7]:
        sec("ASOs – Atestados de Saúde Ocupacional")
        tabela_editavel("asos",
            [("nome","IOE"),("ultimo","Último ASO"),("validade","Validade")], sort_by="nome")

        # Validação: IOEs cadastrados × ASOs (exclui Responsáveis/titulares)
        _todos_ioes: set = set()
        for _campo in ["equipes_medicos","equipes_fisicos","equipes_tecnicos",
                       "equipes_dosimetristas","equipes_enfermagem","equipes_demais"]:
            for _p in d.get(_campo, []):
                _n = (_p.get("nome") or "").strip()
                if _n:
                    _todos_ioes.add(_n)
        if _todos_ioes:
            sec("Validação IOEs × ASOs")
            _nomes_aso = {(r.get("nome") or "").strip() for r in d.get("asos", [])}
            _com_aso = _todos_ioes & _nomes_aso
            _sem_aso = _todos_ioes - _nomes_aso
            _c1, _c2 = st.columns(2)
            _c1.metric("IOEs com ASO ✅", len(_com_aso))
            _c2.metric("IOEs sem ASO ⚠️", len(_sem_aso))
            if _sem_aso:
                st.warning("**IOEs sem ASO cadastrado:**")
                for _nome in sorted(_sem_aso):
                    st.markdown(f"• {_nome}")
            else:
                st.success("✅ Todos os IOEs possuem ASO cadastrado!")


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 3 – EQUIPAMENTOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    avisos_tab([
        {"label": "Equipamentos / Fontes de Radiação",  "ok": len(d.get("equipamentos",[])) > 0,       "critico": True},
        {"label": "Conjuntos dosimétricos",             "ok": len(d.get("conjunto_dosimetrico",[])) > 0,"critico": True},
        {"label": "Instrumentos de medição",            "ok": len(d.get("instrumentos_medicao",[])) > 0,"critico": False},
        {"label": "Monitores de área",                  "ok": len(d.get("monitores_area",[])) > 0,      "critico": False},
        {"label": "Fantomas",                           "ok": len(d.get("fantomas",[])) > 0,            "critico": False},
    ])
    sub = st.tabs(["☢️ Fontes de Radiação", "🔋 Fontes de Referência",
                   "🔬 Conj. Dosimétricos", "📏 Instrumentos",
                   "🧊 Fantomas", "📡 Monitores de Área", "🖥️ Outros"])

    with sub[0]:
        sec("Equipamentos / Fontes Emissoras de Radiação Ionizante")
        tabela_editavel("equipamentos", [
            ("nome","Nome"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Nº Série"),("fabricacao","Fabricação"),("aceite","Aceite"),
            ("energia","Energia"),("radiacao","Radiação"),("taxa_dose","Taxa de Dose"),
        ])

    with sub[1]:
        sec("Fontes de Referência Seladas")
        tabela_editavel("fontes_referencia", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Série"),("fabricacao","Fabricação"),
            ("atividade","Atividade"),("tipo","Tipo"),
        ])

    with sub[2]:
        sec("Conjuntos Dosimétricos (Câmaras e Eletrômetros)")
        tabela_editavel("conjunto_dosimetrico", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
            ("calibracao","Data Calibração"),("fator","Fator Calibração"),
        ])

    with sub[3]:
        sec("Outros Instrumentos de Medição")
        tabela_editavel("instrumentos_medicao", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
            ("calibracao","Data Calibração"),
        ])

    with sub[4]:
        sec("Fantomas")
        tabela_editavel("fantomas", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("dimensoes","Dimensões"),("material","Material"),
        ])

    with sub[5]:
        sec("Monitores de Área")
        tabela_editavel("monitores_area", [
            ("obj","Item"),("fabricante","Fabricante"),
            ("modelo","Modelo"),("serie","Nº Série"),
            ("calibracao","Data Calibração"),("fator","Fator Calibração"),
        ])

    with sub[6]:
        sec("Outros Detectores / Equipamentos")
        tabela_editavel("outros_detectores", [
            ("obj","Item"),("fabricante","Fabricante"),("modelo","Modelo"),
            ("serie","Nº Série"),("data","Data"),("tipo","Tipo"),
        ])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 4 – GARANTIA DA QUALIDADE
# ───────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    avisos_tab([
        {"label": "Testes diários (Aceleradores)",   "ok": len(d.get("testes_diarios",[])) > 0,          "critico": True},
        {"label": "Testes mensais (Aceleradores)",   "ok": len(d.get("testes_mensais",[])) > 0,          "critico": True},
        {"label": "Testes anuais (Aceleradores)",    "ok": len(d.get("testes_anuais",[])) > 0,           "critico": True},
        {"label": "Testes Braquiterapia",            "ok": len(d.get("testes_diarios_braqui",[])) > 0,   "critico": False},
        {"label": "Testes Ortovoltagem",             "ok": len(d.get("testes_mensais_orto",[])) > 0,     "critico": False},
        {"label": "Sistemas de planejamento",        "ok": len(d.get("sistemas_planejamento",[])) > 0,   "critico": False},
        {"label": "Técnicas de tratamento",          "ok": len(d.get("tecnicas_tratamento",[])) > 0,     "critico": False},
    ])

    sub = st.tabs([
        "🔬 Aceleradores Lineares",
        "💉 Braquiterapia",
        "🔆 Ortovoltagem",
        "🖥️ Sistemas de Planejamento",
        "🎯 Técnicas de Tratamento",
    ])

    with sub[0]:
        sec("Testes Diários – Segurança, Dosimétricos e Mecânicos")
        tabela_editavel("testes_diarios",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])
        sec("Testes Mensais")
        tabela_editavel("testes_mensais",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])
        sec("Testes Anuais")
        tabela_editavel("testes_anuais",
            [("tipo","Tipo"),("teste","Teste"),("tolerancia","Tolerância")])

    with sub[1]:
        sec("Testes Diários – Braquiterapia")
        tabela_editavel("testes_diarios_braqui",
            [("teste","Teste"),("tolerancia","Tolerância")])
        sec("Testes Trimestrais – Braquiterapia")
        tabela_editavel("testes_trimestrais_braqui",
            [("teste","Teste"),("tolerancia","Tolerância")])

    with sub[2]:
        sec("Testes Mensais – Ortovoltagem")
        tabela_editavel("testes_mensais_orto",
            [("teste","Teste"),("tolerancia","Tolerância")])

    with sub[3]:
        sec("Sistemas de Planejamento")
        tabela_editavel("sistemas_planejamento",
            [("nome","Nome"),("fabricante","Fabricante"),
             ("versao","Versão"),("tecnicas","Técnicas")])

    with sub[4]:
        sec("Técnicas de Tratamento")
        tabela_editavel("tecnicas_tratamento",
            [("nome","Nome"),("descricao","Descrição")])


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 5 – TEXTOS DOS CAPÍTULOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    tc = d.get("textos_caps", {})
    avisos_tab([
        {"label": "Classificação de Áreas",       "ok": bool(tc.get("classificacao_areas")),    "critico": True},
        {"label": "Controle de Acesso",           "ok": bool(tc.get("controle_acesso")),        "critico": False},
        {"label": "Monitoração Individual",       "ok": bool(tc.get("monitoracao_individual")), "critico": True},
        {"label": "Monitoração de Áreas",         "ok": bool(tc.get("monitoracao_areas")),      "critico": False},
        {"label": "Controle Médico dos IOEs",     "ok": bool(tc.get("controle_medico")),        "critico": False},
        {"label": "Níveis Operacionais",          "ok": bool(tc.get("niveis_operacionais")),    "critico": False},
        {"label": "Procedimentos de Emergência",  "ok": bool(tc.get("procedimentos_emergencia")),"critico": True},
        {"label": "Programa de Treinamento",      "ok": bool(tc.get("programa_treinamento")),   "critico": False},
        {"label": "Programa de Educação",         "ok": bool(tc.get("programa_educacao")),      "critico": False},
        {"label": "Gerência de Rejeitos",         "ok": bool(tc.get("gerencia_rejeitos")),      "critico": False},
        {"label": "Cálculo de Barreiras",         "ok": bool(tc.get("calculo_barreiras")),      "critico": False},
        {"label": "Matriz de Risco",              "ok": bool(tc.get("matriz_risco")),           "critico": False},
        {"label": "Auditoria Externa",            "ok": bool(tc.get("auditoria_externa")),      "critico": False},
    ])
    textos_conf = [
        ("classificacao_areas",     "Classificação de Áreas"),
        ("controle_acesso",         "Mecanismos de Controle de Acesso"),
        ("monitoracao_individual",  "Monitoração Individual"),
        ("monitoracao_areas",       "Monitoração de Áreas"),
        ("controle_medico",         "Controle Médico dos IOEs"),
        ("niveis_operacionais",     "Níveis Operacionais e Restrições"),
        ("procedimentos_emergencia","Procedimentos de Emergência"),
        ("programa_treinamento",    "Programa de Treinamento em PR"),
        ("programa_educacao",       "Programa de Educação Continuada"),
        ("gerencia_rejeitos",       "Gerência de Rejeitos Radioativos"),
        ("calculo_barreiras",       "Cálculo de Barreiras"),
        ("matriz_risco",            "Matriz de Risco"),
        ("auditoria_externa",       "Auditoria Externa"),
    ]
    st.caption("💡 Textos importados do projeto aparecem pré-preenchidos. Edite conforme necessário.")
    for chave, label in textos_conf:
        preenchido = bool(tc.get(chave, "").strip())
        icone = "✅" if preenchido else "📄"
        with st.expander(f"{icone} {label}", expanded=not preenchido):
            tc[chave] = st.text_area(
                label, tc.get(chave, ""), height=200,
                key=f"tc_{chave}_{sv}",
                label_visibility="collapsed"
            )
    d["textos_caps"] = tc


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 6 – ARQUIVOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    pdfs_importados = d.get("pdfs", {})
    pdfs_bytes_map_check = d.get("_pdfs_bytes", {})
    _secoes_obrig = ["autorizacao_funcionamento", "calculo_blindagem", "sevrra"]
    avisos_tab([
        {"label": f"PDF – {s.replace('_',' ').title()}",
         "ok": _pdf_ok(s, pdfs_bytes_map_check, pdfs_importados),
         "critico": s in _secoes_obrig}
        for s in ["autorizacao_funcionamento","calculo_blindagem","sevrra",
                  "levantamento_radiometrico","auditoria","contrato_monitoracao"]
    ])
    pdfs_bytes_map  = d.get("_pdfs_bytes", {})

    total_vinculados = sum(len(v) for v in pdfs_importados.values() if isinstance(v, list))
    total_uploaded   = len(pdfs_bytes_map)

    # Metric cards
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="m-value">{total_vinculados}</div>
            <div class="m-label">📋 Caminhos vinculados</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="m-value" style="color:#22C55E;">{total_uploaded}</div>
            <div class="m-label">⬆️ Arquivos carregados</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        pendentes = max(0, total_vinculados - total_uploaded)
        cor_p = "#EF4444" if pendentes > 0 else "#22C55E"
        st.markdown(f"""
        <div class="metric-card">
            <div class="m-value" style="color:{cor_p};">{pendentes}</div>
            <div class="m-label">⚠️ Upload pendente</div>
        </div>
        """, unsafe_allow_html=True)

    st.info(
        "**Como funciona:** O projeto original vinculava PDFs por caminho local. "
        "Na versão web, faça **upload** de cada arquivo — eles serão incorporados ao PPR final."
    )
    st.divider()

    secoes_pdf = [
        ("autorizacao_funcionamento",         "Autorização de Funcionamento (CNEN)",  ["pdf"]),
        ("calculo_blindagem",                 "Cálculo de Blindagem",                 ["pdf"]),
        ("levantamento_radiometrico",         "Levantamento Radiométrico",            ["pdf"]),
        ("classificacao_areas",               "Classificação de Áreas",               ["pdf"]),
        ("sevrra",                            "SEVRRA",                               ["pdf"]),
        ("auditoria",                         "Auditoria Dosimétrica",                ["pdf"]),
        ("certificados_conjunto_dosimetrico", "Certificados – Conjuntos Dosimétricos",["pdf"]),
        ("certificados_monitores_area",       "Certificados – Monitores de Área",     ["pdf"]),
        ("certificados_outros",               "Certificados – Outros",                ["pdf"]),
        ("contrato_monitoracao",              "Contrato de Monitoração Individual",   ["pdf"]),
        ("procedimentos_emergencia",          "Procedimentos de Emergência",          ["pdf","png","jpg","jpeg"]),
        ("gerencia_rejeitos",                 "Gerência de Rejeitos",                 ["pdf","png","jpg","jpeg"]),
    ]

    c1, c2 = st.columns(2)
    for i, (chave, label, tipos_sec) in enumerate(secoes_pdf):
        col = c1 if i % 2 == 0 else c2
        with col:
            paths_vinculados = pdfs_importados.get(chave, [])
            paths_vinculados = [p for p in paths_vinculados if p]
            uploaded_nesta_secao = [
                v["nome"] for v in pdfs_bytes_map.values()
                if v.get("chave_secao") == chave
            ]
            n_vinc = len(paths_vinculados)
            n_up   = len(uploaded_nesta_secao)

            if n_up > 0:
                icone = "✅"
            elif n_vinc > 0:
                icone = "⚠️"
            else:
                icone = "📁"

            status_txt = f"{n_up} carregado(s)" if n_up > 0 else (
                f"{n_vinc} vinculado(s) — upload pendente" if n_vinc > 0 else "vazio"
            )

            with st.expander(f"{icone} {label} — {status_txt}", expanded=False):
                if paths_vinculados:
                    st.markdown("**📋 Arquivos do projeto original:**")
                    for p in paths_vinculados:
                        nome_arquivo = p.replace("\\", "/").split("/")[-1]
                        st.caption(f"  📄 {nome_arquivo}")
                    st.markdown("**⬆️ Faça upload dos arquivos acima:**")

                _lbl_up = f"Selecionar arquivo(s) – {label}" if len(tipos_sec) > 1 else f"Selecionar PDF – {label}"
                upload_pdfs(chave, _lbl_up, tipos=tipos_sec)

    # ── ASO no mesmo grid ─────────────────────────────────────────────────────
    # secoes_pdf tem 12 itens (índices 0-11); índice 12 é par → coluna c1
    n_asos = len(d.get("asos", []))
    icone_aso     = "✅" if n_asos > 0 else "📁"
    status_aso_txt = f"{n_asos} ASO(s) extraído(s)" if n_asos > 0 else "vazio"
    with c1:
        with st.expander(
            f"{icone_aso} ASO – Atestados de Saúde Ocupacional — {status_aso_txt}",
            expanded=True,
        ):
            st.caption("Faça upload de um PDF único consolidando todos os ASOs e clique em **Extrair**.")
            aso_up = st.file_uploader(
                "Selecionar PDF – ASOs", type=["pdf"], key="up_aso_extrator"
            )
            # Botão sempre visível; valida presença do arquivo ao clicar
            if st.button("🤖 Extrair e preencher tabela", type="primary", key="btn_extrair_asos"):
                if not aso_up:
                    st.warning("Selecione o PDF dos ASOs antes de extrair.")
                else:
                    with st.status("Extraindo dados dos ASOs…", expanded=True) as aso_status:
                        try:
                            st.write("📖 Lendo o PDF…")
                            pdf_bytes = aso_up.read()
                            st.write("🤖 Consultando IA para identificar os registros…")
                            registros = extrair_asos_do_pdf(pdf_bytes)
                            st.write(f"✅ {len(registros)} ASO(s) identificado(s). Preenchendo tabela…")
                            existentes = {r["nome"]: r for r in d.get("asos", [])}
                            for r in registros:
                                existentes[r["nome"]] = r
                            d["asos"] = list(existentes.values())
                            aso_status.update(
                                label=f"✅ {len(registros)} ASO(s) extraído(s) com sucesso!",
                                state="complete"
                            )
                            st.rerun()
                        except Exception as e:
                            aso_status.update(label="❌ Erro na extração", state="error")
                            st.error(f"Falha ao extrair ASOs: {e}")
            if n_asos > 0:
                st.success(f"{n_asos} registro(s) na tabela. Veja na aba **Pessoal › ASOs**.")

    # ── Logo da Instituição ───────────────────────────────────────────────────
    sec("Logo da Instituição")
    logo_up = st.file_uploader("Imagem do logo (PNG/JPG)", type=["png","jpg","jpeg"], key=f"up_logo_{sv}")
    if logo_up:
        d["_logo_bytes"] = base64.b64encode(logo_up.read()).decode()
        st.success("Logo carregado!")
    if d.get("_logo_bytes"):
        try:
            img_b = base64.b64decode(d["_logo_bytes"])
            st.image(img_b, width=200)
        except Exception:
            pass

    if d.get("_pdfs_bytes"):
        sec("Arquivos Carregados na Sessão")
        por_secao: dict = {}
        for k, v in d["_pdfs_bytes"].items():
            sec_k = v.get("chave_secao","?")
            por_secao.setdefault(sec_k, []).append(v["nome"])
        for s, nomes in por_secao.items():
            st.write(f"**{s}:** " + ", ".join(nomes))

        if st.button("🗑️ Limpar todos os PDFs carregados"):
            d["_pdfs_bytes"] = {}
            d["_logo_bytes"] = None
            st.rerun()


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 7 – VENCIMENTOS
# ───────────────────────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("📅 Vencimentos e Prazos")

    venc = d.setdefault("vencimentos", {k: {"realizacao":"","vencimento":""} for k in [
        "autorizacao_funcionamento","levantamento_radiometrico","auditoria",
        "sevrra","certificados_conjunto_dosimetrico",
        "certificados_outros","certificados_monitores_area",
    ]})

    _docs_venc = [
        ("autorizacao_funcionamento",         "Autorização de Funcionamento"),
        ("levantamento_radiometrico",         "Levantamento Radiométrico"),
        ("auditoria",                         "Auditoria Dosimétrica"),
        ("sevrra",                            "SEVRRA"),
        ("certificados_conjunto_dosimetrico", "Certificados – Conj. Dosimétricos"),
        ("certificados_outros",               "Certificados – Outros"),
        ("certificados_monitores_area",       "Certificados – Monitores de Área"),
    ]

    # ── Extração por IA ──────────────────────────────────────────────────────
    sec("📂 Extrair Datas dos PDFs")
    _pdfs_disp = len([v for v in d.get("_pdfs_bytes",{}).values()
                      if v.get("chave_secao") in dict(_docs_venc)])
    if _pdfs_disp == 0:
        st.info("Faça upload dos PDFs na aba **Arquivos** para habilitar a extração automática de datas.")
    else:
        st.caption(f"{_pdfs_disp} PDF(s) disponível(is) para extração.")
        if st.button("🤖 Extrair datas dos PDFs carregados", type="primary", key="btn_extrair_venc"):
            with st.status("Extraindo datas…", expanded=True) as _vst:
                try:
                    st.write("🤖 Consultando IA para cada documento…")
                    _extraido = extrair_vencimentos_dos_pdfs(d.get("_pdfs_bytes",{}))
                    for k, v in _extraido.items():
                        venc[k] = v
                    d["vencimentos"] = venc
                    _vst.update(label=f"✅ {len(_extraido)} documento(s) processado(s)!", state="complete")
                    st.rerun()
                except Exception as _e:
                    _vst.update(label="❌ Erro na extração", state="error")
                    st.error(str(_e))

    # ── Tabela editável de documentos ────────────────────────────────────────
    sec("Documentos – Realização e Vencimento")

    _hoje_v = datetime.date.today()

    def _status_venc(s: str):
        d_ = _parse_br(s)
        if not d_:
            return "—"
        delta = (d_ - _hoje_v).days
        if delta < 0:
            return f"⛔ Vencido há {-delta}d"
        if delta <= 30:
            return f"🔴 Vence em {delta}d"
        if delta <= 90:
            return f"⚠️ Vence em {delta}d"
        return f"✅ {delta}d restantes"

    _rows_v = []
    for _ck, _cn in _docs_venc:
        _e = venc.get(_ck, {"realizacao":"","vencimento":""})
        _rows_v.append({"Documento": _cn,
                        "Realização": _e.get("realizacao",""),
                        "Vencimento": _e.get("vencimento",""),
                        "Status": _status_venc(_e.get("vencimento",""))})

    _df_v = pd.DataFrame(_rows_v)

    # Edição de datas (realização + vencimento editáveis; status auto)
    _df_edit_v = st.data_editor(
        _df_v[["Documento","Realização","Vencimento"]],
        column_config={
            "Documento":   st.column_config.TextColumn("Documento", disabled=True, width="large"),
            "Realização":  st.column_config.TextColumn("Realização (DD/MM/AAAA)"),
            "Vencimento":  st.column_config.TextColumn("Vencimento (DD/MM/AAAA)"),
        },
        num_rows="fixed",
        use_container_width=True,
        key=f"tbl_venc_{sv}",
    )
    # Salva edições e exibe status ao lado
    for _i, (_ck, _cn) in enumerate(_docs_venc):
        venc[_ck] = {
            "realizacao": str(_df_edit_v.iloc[_i]["Realização"] or ""),
            "vencimento": str(_df_edit_v.iloc[_i]["Vencimento"] or ""),
        }
    d["vencimentos"] = venc

    # Status summary — styled HTML table with chips
    def _chip_html(status_str: str) -> str:
        s = status_str
        if s == "—":
            return "<span class='chip chip-none'>—</span>"
        if s.startswith("⛔"):
            return f"<span class='chip chip-expired'>{s}</span>"
        if s.startswith("🔴"):
            return f"<span class='chip chip-alert'>{s}</span>"
        if s.startswith("⚠️"):
            return f"<span class='chip chip-warn'>{s}</span>"
        return f"<span class='chip chip-ok'>{s}</span>"

    # Usa _df_edit_v (pós-edição) para que os chips reflitam o que o usuário acabou de digitar
    _rows_display = [
        {"Documento": _docs_venc[_i][1],
         "Realização": str(_df_edit_v.iloc[_i]["Realização"] or ""),
         "Vencimento": str(_df_edit_v.iloc[_i]["Vencimento"] or ""),
         "Status": _status_venc(str(_df_edit_v.iloc[_i]["Vencimento"] or ""))}
        for _i in range(len(_docs_venc))
    ]
    _trs = ""
    for _row in _rows_display:
        _trs += (
            f"<tr>"
            f"<td style='font-weight:500;'>{_he(_row['Documento'])}</td>"
            f"<td>{_he(_row['Realização']) or '—'}</td>"
            f"<td>{_he(_row['Vencimento']) or '—'}</td>"
            f"<td>{_chip_html(_row['Status'])}</td>"
            f"</tr>"
        )
    st.markdown(
        f"<div class='venc-wrap'><table class='venc-table'>"
        f"<thead><tr><th>Documento</th><th>Realização</th><th>Vencimento</th><th>Status</th></tr></thead>"
        f"<tbody>{_trs}</tbody></table></div>",
        unsafe_allow_html=True,
    )

    # ── ASOs vencendo primeiro (top 10) ──────────────────────────────────────
    sec("🩺 ASOs – 10 Próximos Vencimentos")

    _asos_all = d.get("asos", [])
    if not _asos_all:
        st.info("Nenhum ASO cadastrado. Preencha em **Pessoal › ASOs**.")
    else:
        def _sort_key(r):
            d_ = _parse_br(r.get("validade",""))
            return d_ if d_ else datetime.date(9999,12,31)

        _asos_sorted = sorted(_asos_all, key=_sort_key)[:10]
        _aso_rows = []
        for _r in _asos_sorted:
            _vd = _parse_br(_r.get("validade",""))
            if not _vd:
                _st = "—"; _bg = ""
            else:
                _delta = (_vd - _hoje_v).days
                if _delta < 0:
                    _st = f"⛔ Vencido há {-_delta}d"
                elif _delta <= 30:
                    _st = f"🔴 Vence em {_delta}d"
                elif _delta <= 90:
                    _st = f"⚠️ Vence em {_delta}d"
                else:
                    _st = f"✅ {_delta}d"
            _aso_rows.append({
                "IOE": _r.get("nome",""),
                "Último ASO": _r.get("ultimo",""),
                "Validade": _r.get("validade",""),
                "Status": _st,
            })
        _aso_trs = ""
        for _row in _aso_rows:
            _s = _row["Status"]
            if _s.startswith("⛔"):
                _chip_cls = "chip-expired"
            elif _s.startswith("🔴"):
                _chip_cls = "chip-alert"
            elif _s.startswith("⚠️"):
                _chip_cls = "chip-warn"
            elif _s == "—":
                _chip_cls = "chip-none"
            else:
                _chip_cls = "chip-ok"
            _aso_trs += (
                f"<tr>"
                f"<td style='font-weight:500;'>{_he(_row['IOE'])}</td>"
                f"<td>{_he(_row['Último ASO']) or '—'}</td>"
                f"<td>{_he(_row['Validade']) or '—'}</td>"
                f"<td><span class='chip {_chip_cls}'>{_he(_s)}</span></td>"
                f"</tr>"
            )
        st.markdown(
            f"<div class='venc-wrap'><table class='venc-table'>"
            f"<thead><tr><th>IOE</th><th>Último ASO</th><th>Validade</th><th>Status</th></tr></thead>"
            f"<tbody>{_aso_trs}</tbody></table></div>",
            unsafe_allow_html=True,
        )


# ───────────────────────────────────────────────────────────────────────────────
#  TAB 8 – GERAR PDF
# ───────────────────────────────────────────────────────────────────────────────
with tabs[7]:
    st.subheader("📑 Geração do Plano de Proteção Radiológica")
    inst_v = d["instalacao"]

    pct, itens = calcular_progresso(d)
    criticos_faltando = erros_criticos(itens)

    col_check, col_gerar = st.columns([3, 2])

    with col_check:
        sec("✅ Checklist de Completude")

        grupos = [
            ("🏥 Identificação",      itens[0:6]),
            ("👤 Responsáveis",       itens[6:11]),
            ("👥 Equipes",            itens[11:14]),
            ("⚙️ Equipamentos",       itens[14:17]),
            ("✅ Garantia Qualidade", itens[17:21]),
            ("📝 Textos",             itens[21:]),
        ]
        for titulo_grp, grupo in grupos:
            ok_grp    = sum(1 for i in grupo if i["ok"])
            total_grp = len(grupo)
            cor_grp   = "🟢" if ok_grp == total_grp else "🟡" if ok_grp > 0 else "🔴"
            with st.expander(f"{cor_grp} {titulo_grp} — {ok_grp}/{total_grp}", expanded=(ok_grp < total_grp)):
                for item in grupo:
                    icon   = "✅" if item["ok"] else ("❌" if item["critico"] else "⚠️")
                    sufixo = " *(obrigatório)*" if item["critico"] and not item["ok"] else ""
                    st.markdown(f"{icon} {item['label']}{sufixo}")

    with col_gerar:
        sec("📊 Status do Projeto")

        # Metric cards grid
        cor_pct = "#22C55E" if pct >= 80 else "#F59E0B" if pct >= 50 else "#EF4444"
        st.markdown(f"""
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:12px;">
            <div class="metric-card">
                <div class="m-value" style="color:{cor_pct};">{pct}%</div>
                <div class="m-label">Preenchimento</div>
            </div>
            <div class="metric-card">
                <div class="m-value" style="color:#22C55E;">{sum(1 for i in itens if i["ok"])}</div>
                <div class="m-label">✅ OK</div>
            </div>
            <div class="metric-card">
                <div class="m-value" style="color:#EF4444;">{len(itens) - sum(1 for i in itens if i["ok"])}</div>
                <div class="m-label">❌ Faltando</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if criticos_faltando:
            faltando_txt = "\n".join(f"- {i['label']}" for i in criticos_faltando)
            st.error(f"**{len(criticos_faltando)} campo(s) obrigatório(s) faltando:**\n{faltando_txt}")
        else:
            st.success("Todos os campos obrigatórios preenchidos!")

        st.divider()

        # Resumo rápido
        st.markdown("**Resumo do projeto:**")
        st.markdown(f"""
        <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:12px; font-size:0.84rem; color:#374151; line-height:1.8;">
            🏥 <b>{inst_v.get('nome','—')}</b><br>
            📋 CNEN: {inst_v.get('matricula_cnen','—')}<br>
            📍 {inst_v.get('cidade','—')}/{inst_v.get('uf','—')}<br>
            👥 {len(d.get('equipes_medicos',[]))} médicos · {len(d.get('equipes_fisicos',[]))} físicos<br>
            ⚙️ {len(d.get('equipamentos',[]))} equipamentos<br>
            📎 {len(d.get('_pdfs_bytes',{}))} PDFs anexados
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        if criticos_faltando:
            st.warning("Complete os campos obrigatórios (❌) antes de gerar o PDF.")
            gerar_disabled = True
        else:
            gerar_disabled = False

        if st.button("📑 Gerar PDF", type="primary", use_container_width=True,
                     disabled=gerar_disabled):
            try:
                with st.status("⚙️ Elaborando o PPR...", expanded=True) as status:
                    st.write("📋 Verificando e organizando dados...")
                    st.write("🖨️ Renderizando páginas...")
                    from ppr_pdf_web import gerar_pdf_bytes
                    pdf_bytes = gerar_pdf_bytes(d)
                    st.write("✅ Documento finalizado!")
                    status.update(label="✅ PPR gerado com sucesso!", state="complete", expanded=False)
                _nome_pdf_inst = (inst_v.get("nome") or "PPR").replace(" ", "_").replace(",", "")
                _data_pdf = datetime.date.today().strftime("%d-%m-%Y")
                nome_pdf = f"{_nome_pdf_inst}_{_data_pdf}"
                st.session_state["_pdf_gerado"] = {"bytes": pdf_bytes, "nome": nome_pdf}
            except ImportError:
                st.error("❌ Módulo ppr_pdf_web não encontrado.")
            except Exception as e:
                st.error(f"❌ Erro ao gerar PDF: {e}")
                st.exception(e)

        if st.session_state.get("_pdf_gerado"):
            _pdf_info = st.session_state["_pdf_gerado"]
            _pdf_b    = _pdf_info["bytes"]
            _nome_p   = _pdf_info["nome"]

            st.success("✅ PPR pronto para download!")
            st.download_button(
                label="⬇️ Baixar PPR",
                data=_pdf_b,
                file_name=f"PPR_{_nome_p}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

            st.divider()
            sec("☁️ Salvar na Nuvem")
            st.markdown(
                "<div style='background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;"
                "padding:8px 12px;font-size:0.82rem;color:#0369A1;margin-bottom:10px;'>"
                "💡 Baixe o PDF acima e faça upload no serviço desejado, ou abra o Gmail para enviar por e-mail."
                "</div>",
                unsafe_allow_html=True,
            )
            _gc1, _gc2, _gc3 = st.columns(3)
            with _gc1:
                _mailto = f"mailto:?subject=PPR+{_nome_p}&body=Segue+o+Plano+de+Proteção+Radiológica+em+anexo."
                st.link_button("📧 Gmail / E-mail", _mailto, use_container_width=True)
            with _gc2:
                st.link_button("📁 Google Drive", "https://drive.google.com", use_container_width=True)
            with _gc3:
                st.link_button("☁️ OneDrive", "https://onedrive.live.com", use_container_width=True)

        st.caption(
            "Arquivos enviados na aba 'Arquivos' serão incorporados automaticamente ao documento final."
        )
