"""
DICOM RT Plan Viewer - Flask Application
Leitura de arquivos DICOM RT Plan com visualização web e geração de PDF.
"""


import os
import io
import json
import getpass
import uuid
import math
from datetime import date, datetime
from flask import Flask, request, jsonify, send_file, render_template_string


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB


# ─────────────────────────────────────────────────────────────
# TABELAS CONSULTIVAS — ARMAZENAMENTO EM DISCO
# ─────────────────────────────────────────────────────────────


TABLES_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables")
LOGO_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
os.makedirs(TABLES_DIR, exist_ok=True)


def tables_index_path():
    return os.path.join(TABLES_DIR, "_index.json")


def load_tables_index():
    """Retorna dict: {id: {name, category, energia, filename, uploaded_at}}"""
    p = tables_index_path()
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tables_index(idx):
    with open(tables_index_path(), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def parse_table_file(file_bytes, filename):
    """
    Lê Excel (.xlsx) ou CSV e retorna:
      { "cols": [float,...], "rows": [float,...], "data": [[float,...]] }


    Regra de leitura:
      - Cabeçalhos de coluna (tamanho de campo): células B1 até última não-vazia da linha 1
      - Cabeçalhos de linha (profundidade):       células A2 até última não-vazia da coluna A
      - Dados: interseção das linhas × colunas acima
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    raw = None


    # ── .xlsx ────────────────────────────────────────────────────
    if ext == "xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            raw = [[cell.value for cell in row] for row in ws.iter_rows()]
        except Exception as e:
            raise ValueError(f"Erro ao ler .xlsx: {e}")


    # ── .xls (formato binário legado) ───────────────────────────
    elif ext == "xls":
        try:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file_bytes)
            ws = wb.sheet_by_index(0)
            raw = [ws.row_values(r) for r in range(ws.nrows)]
        except ImportError:
            raise ValueError(
                "Arquivo .xls não suportado neste ambiente. "
                "Salve como .xlsx ou .csv e tente novamente."
            )
        except Exception as e:
            raise ValueError(f"Erro ao ler .xls: {e}")


    # ── CSV ──────────────────────────────────────────────────────
    elif ext == "csv":
        try:
            import csv
            for enc in ("utf-8-sig", "latin-1", "cp1252"):
                try:
                    text = file_bytes.decode(enc)
                    break
                except Exception:
                    continue
            sample = text[:2048]
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            raw = list(csv.reader(text.splitlines(), dialect))
        except Exception as e:
            raise ValueError(f"Erro ao ler .csv: {e}")


    else:
        raise ValueError(f"Formato não suportado: .{ext}. Use .xlsx, .xls ou .csv")


    if not raw or len(raw) < 2:
        raise ValueError("Arquivo vazio ou sem dados suficientes.")


    def to_float(v):
        """Converte célula para float, retorna None se não for possível."""
        if v is None or str(v).strip() == "":
            return None
        try:
            return float(str(v).replace(",", ".").strip())
        except Exception:
            return None


    def parse_col_header(v):
        """
        Extrai L numérico de cabeçalhos de coluna.
        Aceita: '6x6', '6X6', '6', 6.0, '10x10', '4.5x4.5', etc.
        Retorna float ou None.
        """
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        # Tenta direto como número
        try:
            return float(s.replace(",", "."))
        except Exception:
            pass
        # Tenta padrão LxL (qualquer separador x/X/*)
        import re
        m = re.match(r'^(\d+[\.,]?\d*)\s*[xX\*]\s*(\d+[\.,]?\d*)$', s)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except Exception:
                pass
        return None


    # ── Cabeçalhos de coluna: linha 1, de B1 até última não-vazia ──
    cols = []
    for cell in raw[0][1:]:          # B1 em diante
        v = parse_col_header(cell)
        if v is None:
            break                    # para na primeira vazia ou não-reconhecível
        cols.append(v)


    if not cols:
        raise ValueError(
            "Nenhum cabeçalho reconhecido em B1. "
            "Esperado: números (ex: 5, 10) ou formato LxL (ex: 5x5, 10x10)."
        )


    # ── Cabeçalhos de linha: coluna A, de A2 até última não-vazia ──
    rows_depth = []
    data       = []
    for row in raw[1:]:              # A2 em diante
        if not row:
            break
        depth = to_float(row[0])
        if depth is None:
            break                    # para na primeira vazia da coluna A
        vals = []
        for i in range(len(cols)):
            idx = i + 1
            v = to_float(row[idx]) if idx < len(row) else None
            vals.append(v)
        rows_depth.append(depth)
        data.append(vals)


    if not rows_depth:
        raise ValueError(
            "Nenhuma profundidade encontrada na coluna A (a partir de A2). "
            "Verifique se os valores de profundidade estão na coluna A."
        )


    return {"cols": cols, "rows": rows_depth, "data": data}




def interp1d(x_list, y_list, x):
    """Interpolação linear 1D com clamp nas bordas."""
    if x <= x_list[0]:  return y_list[0]
    if x >= x_list[-1]: return y_list[-1]
    for i in range(len(x_list) - 1):
        if x_list[i] <= x <= x_list[i+1]:
            t = (x - x_list[i]) / (x_list[i+1] - x_list[i])
            return y_list[i] + t * (y_list[i+1] - y_list[i])
    return y_list[-1]




def tmr_lookup(table_data, field_size_L, depth_cm):
    """
    Interpolação bilinear: dado L (campo equivalente, cm) e profundidade (cm),
    retorna o valor de TMR da tabela.
    """
    cols = table_data["cols"]
    rows = table_data["rows"]
    data = table_data["data"]


    col_vals = []
    for row_vals in data:
        valid = [(c, v) for c, v in zip(cols, row_vals) if v is not None]
        if not valid:
            col_vals.append(None)
            continue
        vc, vv = zip(*valid)
        col_vals.append(interp1d(list(vc), list(vv), field_size_L))


    valid_rows = [(r, v) for r, v in zip(rows, col_vals) if v is not None]
    if not valid_rows:
        return None
    vr, vv = zip(*valid_rows)
    return interp1d(list(vr), list(vv), depth_cm)




def get_tmr_for_beam(energia_str, field_x_cm, field_y_cm, depth_cm):
    """
    Busca a tabela TMR pela energia, calcula L e retorna o TMR interpolado.
    Equação 1: L = 2*X*Y / (X+Y)
    """
    try:
        energia = float(str(energia_str).replace(",", "."))
    except Exception:
        return None


    try:
        X = abs(float(str(field_x_cm).replace(",", ".")))
        Y = abs(float(str(field_y_cm).replace(",", ".")))
        if X + Y == 0:
            return None
        L = (2 * X * Y) / (X + Y)
    except Exception:
        return None


    try:
        depth = float(str(depth_cm).replace(",", "."))
    except Exception:
        return None


    idx = load_tables_index()
    for tid, meta in idx.items():
        if meta.get("category") != "TMR":
            continue
        try:
            e_tab = float(str(meta.get("energia", "")).replace(",", "."))
        except Exception:
            continue
        if abs(e_tab - energia) < 0.01:
            fpath = os.path.join(TABLES_DIR, meta["filename"])
            if not os.path.exists(fpath):
                continue
            with open(fpath, "rb") as f:
                table_data = json.load(f)
            val = tmr_lookup(table_data, L, depth)
            if val is not None:
                return round(val, 4)
    return None




def get_tmrw_for_beam(energia_str, field_x_cm, field_y_cm, depth_cm):
    """Busca tabela TMRw pela energia — mesma lógica do TMR mas categoria 'TMRw'."""
    try:
        energia = float(str(energia_str).replace(",", "."))
    except Exception:
        return None
    try:
        X = abs(float(str(field_x_cm).replace(",", ".")))
        Y = abs(float(str(field_y_cm).replace(",", ".")))
        if X + Y == 0: return None
        L = (2 * X * Y) / (X + Y)
    except Exception:
        return None
    try:
        depth = float(str(depth_cm).replace(",", "."))
    except Exception:
        return None


    idx = load_tables_index()
    for tid, meta in idx.items():
        if meta.get("category") != "TMRw":
            continue
        try:
            e_tab = float(str(meta.get("energia", "")).replace(",", "."))
        except Exception:
            continue
        if abs(e_tab - energia) < 0.01:
            fpath = os.path.join(TABLES_DIR, meta["filename"])
            if not os.path.exists(fpath):
                continue
            with open(fpath, "rb") as f:
                table_data = json.load(f)
            val = tmr_lookup(table_data, L, depth)
            if val is not None:
                return round(val, 4)
    return None




# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÕES DO EQUIPAMENTO (FW, equipamento)
# ─────────────────────────────────────────────────────────────


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"equipamento_fabricante": None, "fw": {}, "fd": {}}
    cfg = {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Migração: fw legado como valor único → dict
    if isinstance(cfg.get("fw"), (int, float)):
        cfg["fw"] = {}
    if "fw" not in cfg or cfg["fw"] is None:
        cfg["fw"] = {}
    if "fd" not in cfg or cfg["fd"] is None:
        cfg["fd"] = {}
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_fw_for_energia(energia_str):
    """Retorna o FW configurado para a energia informada, ou None se não cadastrado."""
    try:
        energia = float(str(energia_str).replace(",", "."))
    except Exception:
        return None
    cfg = load_config()
    fw_dict = cfg.get("fw", {})
    for e_key, fw_val in fw_dict.items():
        try:
            if abs(float(str(e_key).replace(",", ".")) - energia) < 0.01:
                return float(fw_val)
        except Exception:
            continue
    return None




def get_fd_for_energia(energia_str):
    """Retorna o FD configurado para a energia informada, ou None se não cadastrado."""
    try:
        energia = float(str(energia_str).replace(",", "."))
    except Exception:
        return None
    cfg = load_config()
    fd_dict = cfg.get("fd", {})
    for e_key, fd_val in fd_dict.items():
        try:
            if abs(float(str(e_key).replace(",", ".")) - energia) < 0.01:
                return float(fd_val)
        except Exception:
            continue
    return None


def parse_scp_file(file_bytes, filename):
    """
    Lê tabela Scp (1D): coluna A = tamanho de campo L (formato LxL ou número),
    coluna B = valor Scp. Leitura de A2:B_ultimo.
    Retorna: { "fields": [float,...], "values": [float,...] }
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    raw = None


    if ext == "xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            ws = wb.active
            raw = [[cell.value for cell in row] for row in ws.iter_rows()]
        except Exception as e:
            raise ValueError(f"Erro ao ler .xlsx: {e}")
    elif ext == "xls":
        try:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file_bytes)
            ws = wb.sheet_by_index(0)
            raw = [ws.row_values(r) for r in range(ws.nrows)]
        except ImportError:
            raise ValueError("Arquivo .xls não suportado. Salve como .xlsx ou .csv.")
        except Exception as e:
            raise ValueError(f"Erro ao ler .xls: {e}")
    elif ext == "csv":
        try:
            import csv
            for enc in ("utf-8-sig", "latin-1", "cp1252"):
                try:
                    text = file_bytes.decode(enc); break
                except Exception:
                    continue
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
            raw = list(csv.reader(text.splitlines(), dialect))
        except Exception as e:
            raise ValueError(f"Erro ao ler .csv: {e}")
    else:
        raise ValueError(f"Formato não suportado: .{ext}. Use .xlsx, .xls ou .csv")


    if not raw or len(raw) < 2:
        raise ValueError("Arquivo vazio ou sem dados suficientes.")


    def to_float(v):
        if v is None or str(v).strip() == "": return None
        try: return float(str(v).replace(",", ".").strip())
        except: return None


    def parse_field_header(v):
        """Extrai L de LxL ou número direto — mesmo mecanismo do TMR."""
        if v is None or str(v).strip() == "": return None
        s = str(v).strip()
        try: return float(s.replace(",", "."))
        except: pass
        import re
        m = re.match(r'^(\d+[\.,]?\d*)\s*[xX\*]\s*(\d+[\.,]?\d*)$', s)
        if m:
            try: return float(m.group(1).replace(",", "."))
            except: pass
        return None


    # Lê A2:B_ultimo — ignora linha 1 (cabeçalho)
    fields, values = [], []
    for row in raw[1:]:
        if not row or len(row) < 2:
            break
        L = parse_field_header(row[0])
        v = to_float(row[1])
        if L is None or v is None:
            break
        fields.append(L)
        values.append(v)


    if not fields:
        raise ValueError(
            "Nenhum dado encontrado a partir de A2:B2. "
            "Coluna A = tamanho de campo (LxL ou número), coluna B = valor Scp."
        )


    return {"fields": fields, "values": values}




def scp_lookup(table_data, field_size_L):
    """Interpolação linear 1D de Scp dado L."""
    fields = table_data["fields"]
    values = table_data["values"]
    valid  = [(f, v) for f, v in zip(fields, values) if v is not None]
    if not valid:
        return None
    vf, vv = zip(*valid)
    return interp1d(list(vf), list(vv), field_size_L)




def get_scp_for_beam(energia_str, field_x_cm, field_y_cm):
    """
    Busca tabela Scp pela energia, calcula L = 2*X*Y/(X+Y) usando X(cm) e Y(cm),
    e retorna o Scp interpolado.
    """
    try:
        energia = float(str(energia_str).replace(",", "."))
    except Exception:
        return None
    try:
        X = abs(float(str(field_x_cm).replace(",", ".")))
        Y = abs(float(str(field_y_cm).replace(",", ".")))
        if X + Y == 0: return None
        L = (2 * X * Y) / (X + Y)
    except Exception:
        return None


    idx = load_tables_index()
    for tid, meta in idx.items():
        if meta.get("category") != "Scp":
            continue
        try:
            e_tab = float(str(meta.get("energia", "")).replace(",", "."))
        except Exception:
            continue
        if abs(e_tab - energia) < 0.01:
            fpath = os.path.join(TABLES_DIR, meta["filename"])
            if not os.path.exists(fpath):
                continue
            with open(fpath, "rb") as f:
                table_data = json.load(f)
            val = scp_lookup(table_data, L)
            if val is not None:
                return round(val, 4)
    return None
# ─────────────────────────────────────────────────────────────


def parse_dicom(file_bytes):
    """Parse DICOM RT Plan file and extract all required fields."""
    try:
        import pydicom
    except ImportError:
        raise ImportError("pydicom não instalado. Execute: pip install pydicom")


    ds = pydicom.dcmread(io.BytesIO(file_bytes), force=True)


    def get_tag(dataset, *tag_pairs):
        """Navigate nested tags. tag_pairs: [(group,elem), ...]"""
        current = dataset
        for tag in tag_pairs:
            try:
                current = current[tag[0], tag[1]].value
            except (KeyError, AttributeError, TypeError):
                return None
        return current


    def tag_str(dataset, *tag_pairs):
        val = get_tag(dataset, *tag_pairs)
        if val is None:
            return "N/A"
        if hasattr(val, 'original_string'):
            return str(val).strip()
        return str(val).strip()


    def seq(dataset, tag):
        """Get sequence safely."""
        try:
            return dataset[tag[0], tag[1]].value
        except (KeyError, AttributeError):
            return []


    # ── Cabeçalho ──────────────────────────────────────────────
    nome_paciente_raw = tag_str(ds, (0x0010, 0x0010))
    id_paciente   = tag_str(ds, (0x0010, 0x1000))
    if id_paciente == "N/A":
        id_paciente = tag_str(ds, (0x0010, 0x0020))


    # Fix 2: Sexo — normalizar para Masculino / Feminino / Outro
    sexo_raw = tag_str(ds, (0x0010, 0x0040)).upper().strip()
    if sexo_raw == "M":
        sexo = "Masculino"
    elif sexo_raw == "F":
        sexo = "Feminino"
    else:
        sexo = "Outro"


    dob_raw  = tag_str(ds, (0x0010, 0x0030))


    # Fix 1: Instituição — (0008,1040) InstitutionalDepartmentName
    # Se não encontrado no root, busca dentro do primeiro beam (padrão de alguns sistemas de TPS)
    instituicao = tag_str(ds, (0x0008, 0x1040))
    if instituicao == "N/A" and "BeamSequence" in ds:
        instituicao = tag_str(ds.BeamSequence[0], (0x0008, 0x1040))
    if instituicao == "N/A":
        instituicao = tag_str(ds, (0x0008, 0x0080))  # InstitutionName como último fallback


    # Fix 3: Nome — DICOM armazena "SOBRENOME^NOME", inverter para "Nome Sobrenome"
    nome_paciente = "N/A"
    if nome_paciente_raw and nome_paciente_raw != "N/A":
        parts = nome_paciente_raw.replace("^", " ").split()
        if len(parts) >= 2:
            # Primeiro token é sobrenome, restante é nome
            sobrenome = parts[0].capitalize()
            nome_proprio = " ".join(p.capitalize() for p in parts[1:])
            nome_paciente = f"{nome_proprio} {sobrenome}"
        else:
            nome_paciente = nome_paciente_raw.capitalize()


    # Calcular idade
    idade = "N/A"
    if dob_raw and dob_raw != "N/A" and len(dob_raw) == 8:
        try:
            dob = date(int(dob_raw[:4]), int(dob_raw[4:6]), int(dob_raw[6:8]))
            today = date.today()
            idade = str(today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)))
        except Exception:
            pass


    dob_fmt = "N/A"
    if dob_raw and dob_raw != "N/A" and len(dob_raw) == 8:
        try:
            dob_fmt = f"{dob_raw[6:8]}/{dob_raw[4:6]}/{dob_raw[:4]}"
        except Exception:
            dob_fmt = dob_raw


    # ── Plano ───────────────────────────────────────────────────
    nome_plano = tag_str(ds, (0x300a, 0x0003))
    if nome_plano == "N/A":
        nome_plano = tag_str(ds, (0x300a, 0x0002))


    # Dose total: (300a,0010) → (300a,0026) — sem casas decimais
    dose_total = "N/A"
    dose_seq = seq(ds, (0x300a, 0x0010))
    if dose_seq:
        try:
            val = float(dose_seq[0][0x300a, 0x0026].value)
            dose_total = f"{val * 100:.0f}"
        except Exception:
            pass


    # Frações: (300a,0070) → (300a,0078)
    fracoes = "N/A"
    fg_seq = seq(ds, (0x300a, 0x0070))
    if fg_seq:
        try:
            fracoes = str(fg_seq[0][0x300a, 0x0078].value)
        except Exception:
            pass


    # Fix 4: Data de aprovação (300e,0004) — ApprovalStatusDate
    data_aprovacao = "N/A"
    aprov_raw = tag_str(ds, (0x300e, 0x0004))
    if aprov_raw and aprov_raw != "N/A" and len(aprov_raw) >= 8:
        try:
            data_aprovacao = f"{aprov_raw[6:8]}/{aprov_raw[4:6]}/{aprov_raw[:4]}"
        except Exception:
            data_aprovacao = aprov_raw


    # (300e,0008) ReviewerName — quem aprovou o plano
    aprovado_por = tag_str(ds, (0x300e, 0x0008))
    if aprovado_por == "N/A":
        aprovado_por = ""


    # ── Feixes (Beam Sequence) ──────────────────────────────────
    beam_seq = seq(ds, (0x300a, 0x00b0))


    # Montar dict de beams por BeamNumber
    beams_by_number = {}
    for beam in beam_seq:
        try:
            bnum = str(beam[0x300a, 0x00c0].value)
            beams_by_number[bnum] = beam
        except Exception:
            pass


    # Coletar dose por beam de FractionGroupSequence → ReferencedBeamSequence
    dose_by_beam = {}
    um_by_beam   = {}
    if fg_seq:
        for fg in fg_seq:
            ref_beams = []
            try:
                ref_beams = fg[0x300c, 0x0004].value
            except (KeyError, AttributeError):
                pass
            for rb in ref_beams:
                try:
                    bref = str(rb[0x300c, 0x0006].value)
                    dose_val = float(rb[0x300a, 0x0084].value) * 100
                    dose_by_beam[bref] = f"{dose_val:.1f}"   # Fix 7: 1 casa decimal
                except Exception:
                    pass
                try:
                    bref = str(rb[0x300c, 0x0006].value)
                    um_val = float(rb[0x300a, 0x0086].value)
                    um_by_beam[bref] = f"{um_val:.1f}"       # Fix 8: 1 casa decimal
                except Exception:
                    pass


    # ── Função auxiliar: somatório ponderado por CP ─────────────
    def calc_soma_cps(beam_obj, energia, dose_f, fd_f, usar_impares=True):
        """
        Soma ponderada por CP.
        usar_impares=True  → soma CPs com índice ímpar   (STATIC)
        usar_impares=False → soma todos os CPs exceto o 0 (DYNAMIC)
        Retorna (soma, debug_str).
        """
        debug = []


        def read_depth(cp):
            """Lê profundidade de (300c,0050)→(300a,0089), float32 ou DS."""
            try:
                for rd in cp[0x300c, 0x0050].value:
                    try:
                        raw_d = rd[0x300a, 0x0089].value
                        return float(raw_d) / 10.0
                    except Exception:
                        continue
            except Exception:
                pass
            return None


        def read_jaw(cp):
            """Lê Xi e Yi do jaw. Aceita (300a,00b8) ou (300a,011e) como DeviceType.
               Retorna (xi_cm, yi_cm) ou (None, None)."""
            xi = yi = None
            idx_jaw = 0
            try:
                for bc in cp[0x300a, 0x011a].value:
                    rt = ""
                    for dev_tag in [(0x300a, 0x00b8), (0x300a, 0x011e)]:
                        try:
                            rt = str(bc[dev_tag[0], dev_tag[1]].value).upper().strip()
                            break
                        except Exception:
                            continue
                    if "MLC" in rt:
                        continue
                    try:
                        raw = bc[0x300a, 0x011c].value
                        if hasattr(raw, '__iter__') and not isinstance(raw, str):
                            pv = [float(v) for v in raw]
                        else:
                            pv = [float(v) for v in str(raw).replace(' ', '').split('\\') if v.strip()]
                    except Exception:
                        continue
                    if len(pv) < 2:
                        continue
                    if 'ASYMX' in rt or ('X' in rt and 'Y' not in rt) or idx_jaw == 0:
                        xi = abs(pv[1] - pv[0]) / 10.0
                        idx_jaw = 1
                    elif 'ASYMY' in rt or 'Y' in rt or idx_jaw == 1:
                        yi = abs(pv[1] - pv[0]) / 10.0
                        idx_jaw = 2
                    if xi is not None and yi is not None:
                        break
            except Exception:
                pass
            return xi, yi


        try:
            cp_list = beam_obj[0x300a, 0x0111].value
            debug.append(f"NCP={len(cp_list)}")
            soma    = 0.0
            prev_mw = 0.0
            n_contrib = 0
            last_xi = last_yi = None   # herança de jaw do CP anterior


            for cp in cp_list:
                try:
                    cp_idx = int(cp[0x300a, 0x0112].value)
                except Exception:
                    debug.append("cp_idx fail"); continue


                # Lê jaw deste CP; se vazio herda do anterior
                xi_cp, yi_cp = read_jaw(cp)
                if xi_cp is not None and yi_cp is not None:
                    last_xi, last_yi = xi_cp, yi_cp
                else:
                    xi_cp, yi_cp = last_xi, last_yi


                if usar_impares and cp_idx % 2 == 0:
                    continue
                if not usar_impares and cp_idx == 0:
                    prev_mw = 0.0; continue


                # Mw
                try:
                    mw = float(cp[0x300a, 0x0134].value)
                except Exception:
                    debug.append(f"CP{cp_idx}:Mw fail"); continue
                dMw = mw - prev_mw
                prev_mw = mw
                if dMw <= 0:
                    debug.append(f"CP{cp_idx}:dMw={dMw:.4f}<=0 skip"); continue


                # Profundidade
                depth_cm = read_depth(cp)
                if depth_cm is None:
                    debug.append(f"CP{cp_idx}:depth=None → return None")
                    return None, " | ".join(debug)


                if xi_cp is None or yi_cp is None or (xi_cp + yi_cp) == 0:
                    debug.append(f"CP{cp_idx}:jaw=({xi_cp},{yi_cp}) → return None")
                    return None, " | ".join(debug)


                tmr_cp = get_tmr_for_beam(energia, xi_cp, yi_cp, depth_cm)
                scp_cp = get_scp_for_beam(energia, xi_cp, yi_cp)


                if tmr_cp is None:
                    debug.append(f"CP{cp_idx}:TMR=None(e={energia},xi={xi_cp:.2f},yi={yi_cp:.2f},d={depth_cm:.2f}) → return None")
                    return None, " | ".join(debug)
                if scp_cp is None:
                    debug.append(f"CP{cp_idx}:Scp=None → return None")
                    return None, " | ".join(debug)
                if tmr_cp * scp_cp * fd_f == 0:
                    debug.append(f"CP{cp_idx}:denom=0"); continue


                parc = dMw * dose_f / (tmr_cp * scp_cp * fd_f)
                soma += parc
                n_contrib += 1
                debug.append(f"CP{cp_idx}:dMw={dMw:.3f},xi={xi_cp:.2f},yi={yi_cp:.2f},d={depth_cm:.2f},TMR={tmr_cp:.4f},Scp={scp_cp:.4f},parc={parc:.2f}")


            debug.append(f"OK:n={n_contrib},soma={soma:.4f}")
            return soma, " | ".join(debug)
        except Exception as e:
            return None, f"exception:{e}"


    # ── Montar lista de campos ──────────────────────────────────
    campos = []
    for beam in beam_seq:
        try:
            bnum = str(beam[0x300a, 0x00c0].value)
        except Exception:
            bnum = "N/A"


        def bs(tag_pair):
            try:
                return str(beam[tag_pair[0], tag_pair[1]].value).strip()
            except Exception:
                return "N/A"


        # Fix 5: Nome do campo — (300a,00c2) BeamDescription é a tag correta
        # (300a,0002) é BeamName (mais curto), (300a,00c2) é BeamDescription (ME-E1 etc.)
        nome_campo = bs((0x300a, 0x00c2))
        if nome_campo == "N/A":
            nome_campo = bs((0x300a, 0x0002))


        feixe_tipo = bs((0x300a, 0x00c6))
        tecnica    = bs((0x300a, 0x00c4))
        equipamento_name = bs((0x300a, 0x00b2))


        # Energia: (300a,0111) → primeira CP → (300a,0114)
        energia = "N/A"
        try:
            cp_seq = beam[0x300a, 0x0111].value
            if cp_seq:
                energia = str(cp_seq[0][0x300a, 0x0114].value)
        except Exception:
            pass


        # Jaw / campo X e Y: (300a,0111) → primeira CP → (300a,011a) → (300a,011c)
        # Converter de mm para cm dividindo por 10 — 1 casa decimal
        campo_x1 = campo_x2 = campo_y1 = campo_y2 = "N/A"
        campo_x_cm = campo_y_cm = "N/A"
        try:
            cp_seq = beam[0x300a, 0x0111].value
            if cp_seq:
                bc_seq = cp_seq[0][0x300a, 0x011a].value
                idx = 0
                for bc in bc_seq:
                    rt_type = str(bc[0x300a, 0x011e].value).upper() if (0x300a, 0x011e) in bc else ""
                    try:
                        positions = bc[0x300a, 0x011c].value
                    except Exception:
                        continue
                    if "X" in rt_type or idx == 0:
                        if len(positions) >= 2:
                            x1_mm = float(positions[0])
                            x2_mm = float(positions[1])
                            campo_x1   = f"{x1_mm / 10:.1f}"
                            campo_x2   = f"{x2_mm / 10:.1f}"
                            campo_x_cm = f"{(x2_mm - x1_mm) / 10:.1f}"
                        idx = 1
                    elif "Y" in rt_type or idx == 1:
                        if len(positions) >= 2:
                            y1_mm = float(positions[0])
                            y2_mm = float(positions[1])
                            campo_y1   = f"{y1_mm / 10:.1f}"
                            campo_y2   = f"{y2_mm / 10:.1f}"
                            campo_y_cm = f"{(y2_mm - y1_mm) / 10:.1f}"
                        idx = 2
                    else:
                        idx += 1
        except Exception:
            pass


        dose_campo = dose_by_beam.get(bnum, "N/A")
        um_campo   = um_by_beam.get(bnum, "N/A")


        # Profundidade: BeamDosePointEquivalentDepth (300a,0089)
        profundidade_cm = "N/A"
        try:
            cp_seq_d = beam[0x300a, 0x0111].value
            if cp_seq_d:
                cp0 = cp_seq_d[0]
                ref_dose_seq = cp0[0x300c, 0x0050].value
                depth_mm = None
                for rd_item in ref_dose_seq:
                    try:
                        depth_mm = float(rd_item[0x300a, 0x0089].value)
                        break
                    except (KeyError, TypeError):
                        continue
                if depth_mm is not None:
                    profundidade_cm = f"{depth_mm / 10:.1f}"
        except Exception:
            pass


        # Filtro virtual (Wedge): detecta presença via (300a,00d0) NumberOfWedges
        # O ângulo real NÃO é lido da tag (tag sempre retorna 60 independente do valor real)
        # k será informado pelo usuário após a análise
        filtro_presente = False
        filtro_val = "—"
        try:
            n_wedges = int(beam[0x300a, 0x00d0].value)
            if n_wedges > 0:
                filtro_presente = True
                # Tenta ler nome/tipo do filtro para exibição
                try:
                    wedge_seq = beam[0x300a, 0x00d1].value
                    if wedge_seq:
                        nome_filtro = str(wedge_seq[0][0x300a, 0x00d4].value).strip()
                        filtro_val = nome_filtro if nome_filtro else "W?"
                except Exception:
                    filtro_val = "W?"
        except Exception:
            pass


        # TMR interpolado
        tmr_val = "N/A"
        if profundidade_cm != "N/A" and campo_x_cm != "N/A" and campo_y_cm != "N/A":
            try:
                tmr_result = get_tmr_for_beam(
                    energia, float(campo_x_cm), float(campo_y_cm), float(profundidade_cm)
                )
                if tmr_result is not None:
                    tmr_val = f"{tmr_result:.4f}"
            except Exception:
                pass


        # TMRw interpolado — só calcula se houver filtro (k virá do usuário depois)
        tmrw_val = "N/A"
        if filtro_presente and profundidade_cm != "N/A" and campo_x_cm != "N/A" and campo_y_cm != "N/A":
            try:
                tmrw_result = get_tmrw_for_beam(
                    energia, float(campo_x_cm), float(campo_y_cm), float(profundidade_cm)
                )
                if tmrw_result is not None:
                    tmrw_val = f"{tmrw_result:.4f}"
            except Exception:
                pass


        # Scp interpolado
        scp_val = "N/A"
        if campo_x_cm != "N/A" and campo_y_cm != "N/A":
            try:
                scp_result = get_scp_for_beam(energia, float(campo_x_cm), float(campo_y_cm))
                if scp_result is not None:
                    scp_val = f"{scp_result:.4f}"
            except Exception:
                pass


        # ── UM (Calc.) — fórmula geral com subcampos ────────────────
        # alpha = 1 se STATIC, 0 se DYNAMIC
        # beta  = 0 se STATIC, 1 se DYNAMIC
        # Sem filtro (k=0):
        #   UM = alpha * Σ_i_ímpares [ (Mwi-Mwi-1)*Dose/(TMRi*Scpi*FD) ]
        #      + beta  * Σ_j_todos   [ (Mwj-Mwj-1)*Dose/(TMRj*Scpj*FD) ]
        # Com filtro (k>0, via /recalc):
        #   UM = k*(Dose/(TMRw*Scp*FW*FD)) + (1-k)*[alpha*Σ_i + beta*Σ_j]


        tecnica_upper = tecnica.upper() if tecnica and tecnica != "N/A" else ""
        alpha = 1 if tecnica_upper == "STATIC"  else 0
        beta  = 1 if tecnica_upper == "DYNAMIC" else 0


        # ── Salva dados por CP para uso no /recalc ──────────────────
        segmentos_cp = []
        try:
            cp_list_seg = beam[0x300a, 0x0111].value
            prev_mw_seg = 0.0
            last_xi_seg = last_yi_seg = None
            for cp_s in cp_list_seg:
                try: cp_idx_s = int(cp_s[0x300a, 0x0112].value)
                except: continue
                # Jaw (herda se vazio)
                xi_s = yi_s = None
                try:
                    for bc in cp_s[0x300a, 0x011a].value:
                        rt = ""
                        for dev_tag in [(0x300a, 0x00b8), (0x300a, 0x011e)]:
                            try: rt = str(cp_s[dev_tag[0],dev_tag[1]].value).upper(); break
                            except: pass
                            try: rt = str(bc[dev_tag[0],dev_tag[1]].value).upper(); break
                            except: pass
                        if "MLC" in rt: continue
                        try:
                            raw = bc[0x300a, 0x011c].value
                            pv = [float(v) for v in raw] if hasattr(raw,'__iter__') and not isinstance(raw,str) else [float(v) for v in str(raw).replace(' ','').split('\\') if v.strip()]
                        except: continue
                        if len(pv) < 2: continue
                        if 'ASYMX' in rt or ('X' in rt and 'Y' not in rt) or xi_s is None:
                            xi_s = abs(pv[1]-pv[0])/10.0
                        elif 'ASYMY' in rt or 'Y' in rt:
                            yi_s = abs(pv[1]-pv[0])/10.0
                        if xi_s and yi_s: break
                except: pass
                if xi_s is not None: last_xi_seg = xi_s
                if yi_s is not None: last_yi_seg = yi_s
                xi_s = xi_s or last_xi_seg
                yi_s = yi_s or last_yi_seg
                # Mw
                try: mw_s = float(cp_s[0x300a, 0x0134].value)
                except: continue
                dMw_s = mw_s - prev_mw_seg
                prev_mw_seg = mw_s
                # Depth
                depth_s = None
                try:
                    for rd in cp_s[0x300c, 0x0050].value:
                        try:
                            raw_d = rd[0x300a, 0x0089].value
                            depth_s = float(raw_d)/10.0; break
                        except: continue
                except: pass
                segmentos_cp.append({
                    "cp_idx":   cp_idx_s,
                    "Mw":       mw_s,
                    "dMw":      dMw_s,
                    "xi":       xi_s,
                    "yi":       yi_s,
                    "depth_cm": depth_s,
                })
        except Exception:
            segmentos_cp = []
        um_calc_val  = "N/A"
        diff_pct_val = "N/A"
        um_calc_debug = ""
        if not filtro_presente:
            try:
                fd = get_fd_for_energia(energia)
                if dose_campo == "N/A":
                    um_calc_debug = "dose=N/A"
                elif fd is None:
                    um_calc_debug = f"FD não cadastrado para energia={energia}"
                else:
                    dose_f = float(dose_campo)
                    fd_f   = float(fd)


                    if alpha == 1:
                        soma, dbg = calc_soma_cps(beam, energia, dose_f, fd_f, usar_impares=True)
                    else:
                        soma, dbg = calc_soma_cps(beam, energia, dose_f, fd_f, usar_impares=False)
                    um_calc_debug = dbg


                    if soma is not None:
                        um_calc = soma
                        um_calc_val = f"{um_calc:.1f}"
                        if um_campo != "N/A":
                            um_tps_f = float(um_campo)
                            if um_tps_f != 0:
                                diff = (um_calc - um_tps_f) / um_tps_f * 100
                                diff_pct_val = f"{diff:.1f}"
                    else:
                        um_calc_debug = "soma=None (tabela TMR/Scp não encontrada, jaw ou profundidade ausente no CP)"
            except Exception as _e:
                um_calc_debug = f"exception: {_e}"


        campos.append({
            "numero":          bnum,
            "nome":            nome_campo,
            "equipamento":     equipamento_name,
            "feixe":           feixe_tipo,
            "energia":         energia,
            "filtro":          filtro_val,
            "filtro_presente": filtro_presente,
            "angulo_filtro":   None,
            "tecnica":         tecnica,
            "alpha":           alpha,
            "beta":            beta,
            "campo_x1":        campo_x1,
            "campo_x2":        campo_x2,
            "campo_y1":        campo_y1,
            "campo_y2":        campo_y2,
            "campo_x_cm":      campo_x_cm,
            "campo_y_cm":      campo_y_cm,
            "profundidade":    profundidade_cm,
            "dose":            dose_campo,
            "tmr":             tmr_val,
            "tmrw":            tmrw_val,
            "scp":             scp_val,
            "um":              um_campo,
            "um_calc":         um_calc_val,
            "diff_pct":        diff_pct_val,
            "um_calc_debug":   um_calc_debug,
            "segmentos_cp":    segmentos_cp,
        })


    # Equipamento principal (primeiro beam)
    equip_display = "N/A"
    if beam_seq:
        try:
            equip_display = str(beam_seq[0][0x300a, 0x00b2].value).strip()
        except Exception:
            pass


    return {
        "instituicao":      instituicao,
        "equipamento":      equip_display,
        "nome_paciente":    nome_paciente,
        "id_paciente":      id_paciente,
        "sexo":             sexo,
        "dob":              dob_fmt,
        "idade":            idade,
        "nome_plano":       nome_plano,
        "dose_total":       dose_total,
        "fracoes":          fracoes,
        "data_aprovacao":   data_aprovacao,
        "aprovado_por":     aprovado_por,
        "campos":           campos,
    }




# ─────────────────────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────────────────────


def generate_pdf(data):
    """Generate a clean, printer-friendly PDF report — landscape A4."""
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


    # Fix 9: Paisagem
    PAGE_SIZE = landscape(A4)
    buf = io.BytesIO()


    doc = SimpleDocTemplate(
        buf, pagesize=PAGE_SIZE,
        leftMargin=16*mm, rightMargin=16*mm,
        topMargin=14*mm, bottomMargin=18*mm,
        title="Relatório RT Plan",
    )


    # ── Paleta monocromática para economia de toner ─────────────
    PRETO   = colors.HexColor("#000000")
    CINZA_E = colors.HexColor("#2b2b2b")
    CINZA_M = colors.HexColor("#555555")
    CINZA_L = colors.HexColor("#dddddd")
    BRANCO  = colors.HexColor("#ffffff")


    styles = getSampleStyleSheet()


    def st(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)


    # Fix 9: alinhamento à esquerda (TA_LEFT) em todos os estilos fora da tabela
    S_TITLE   = st("S_TITLE",   fontName="Helvetica-Bold", fontSize=14,
                   textColor=PRETO, leading=18, spaceAfter=4, alignment=TA_LEFT)
    S_SECTION = st("S_SECTION", fontName="Helvetica-Bold", fontSize=9,
                   textColor=BRANCO, leading=13, alignment=TA_LEFT)
    S_LABEL   = st("S_LABEL",   fontName="Helvetica-Bold", fontSize=8,
                   textColor=CINZA_E, alignment=TA_LEFT)
    S_VALUE   = st("S_VALUE",   fontName="Helvetica",      fontSize=8,
                   textColor=PRETO, alignment=TA_LEFT)
    S_SMALL   = st("S_SMALL",   fontName="Helvetica",      fontSize=7,
                   textColor=CINZA_M, alignment=TA_LEFT)
    S_FOOT    = st("S_FOOT",    fontName="Helvetica",      fontSize=7,
                   textColor=CINZA_M, alignment=TA_CENTER)
    S_TH      = st("S_TH",      fontName="Helvetica-Bold", fontSize=7,
                   textColor=BRANCO, alignment=TA_CENTER)
    S_TD      = st("S_TD",      fontName="Helvetica",      fontSize=7,
                   textColor=PRETO, alignment=TA_CENTER)


    story = []


    # ── Helpers ─────────────────────────────────────────────────
    def section_header(title):
        t = Table([[Paragraph(title, S_SECTION)]], colWidths=[doc.width])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), CINZA_E),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 3))


    def info_row(items, value_widths=None):
        """
        Cada item = [LABEL | VALOR] lado a lado na mesma linha.
        value_widths: lista opcional de larguras de valor por item (mm).
        """
        LABEL_W = 26 * mm
        if value_widths is None:
            block_w = doc.width / len(items)
            value_widths = [block_w - LABEL_W] * len(items)


        cells = []
        col_widths = []
        for (lbl, val), vw in zip(items, value_widths):
            cells.append(Paragraph(lbl, S_LABEL))
            cells.append(Paragraph(str(val), S_VALUE))
            col_widths.extend([LABEL_W, vw])


        t = Table([cells], colWidths=col_widths)
        t.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('TOPPADDING',    (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING',   (0,0), (-1,-1), 3),
            ('RIGHTPADDING',  (0,0), (-1,-1), 2),
        ]))
        story.append(t)


    # ── Título com logo à direita ────────────────────────────────
    logo_file = None
    for ext in ("png", "jpg", "jpeg"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"logo.{ext}")
        if os.path.exists(p):
            logo_file = p
            break


    LOGO_H = 16 * mm   # altura fixa da logo
    LOGO_W = 50 * mm   # largura máxima da logo


    if logo_file:
        from reportlab.platypus import Image as RLImage
        try:
            logo_elem = RLImage(logo_file, width=LOGO_W, height=LOGO_H, kind='proportional')
        except Exception:
            logo_elem = None
    else:
        logo_elem = None


    # Cabeçalho: título à esquerda, logo à direita na mesma linha
    titulo_para   = Paragraph("Relatório de Plano de Tratamento", S_TITLE)
    subtitulo_para = Paragraph(
        f"RT Plan DICOM &nbsp;|&nbsp; Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        S_SMALL
    )


    if logo_elem:
        TITLE_W = doc.width - LOGO_W - 4*mm
        header_tbl = Table(
            [[titulo_para,   logo_elem],
             [subtitulo_para, '']],
            colWidths=[TITLE_W, LOGO_W + 4*mm],
        )
        header_tbl.setStyle(TableStyle([
            ('VALIGN',        (0,0),(0,1),'TOP'),
            ('VALIGN',        (1,0),(1,0),'MIDDLE'),
            ('ALIGN',         (1,0),(1,0),'RIGHT'),
            ('SPAN',          (1,0),(1,1)),
            ('LEFTPADDING',   (0,0),(-1,-1),0),
            ('RIGHTPADDING',  (0,0),(-1,-1),0),
            ('TOPPADDING',    (0,0),(-1,-1),0),
            ('BOTTOMPADDING', (0,0),(-1,-1),2),
        ]))
        story.append(header_tbl)
    else:
        story.append(titulo_para)
        story.append(subtitulo_para)


    story.append(HRFlowable(width="100%", thickness=1.2, color=PRETO, spaceAfter=6))


    # ── Bloco Instituição / Paciente ────────────────────────────
    LABEL_W = 26 * mm


    # Dimensões da foto 3x4 reduzida 1/3 na altura (proporção mantida)
    FOTO_H  = 42 * mm * (2/3)          # altura reduzida 1/3
    FOTO_W  = FOTO_H * (3/4)           # largura proporcional 3:4
    INFO_W  = doc.width - FOTO_W


    # Cada linha deve ter altura = FOTO_H / 3 para as 3 linhas somarem FOTO_H
    # Altura de cada linha = text (~8pt) + top_pad + bot_pad
    # FOTO_H em pontos = 32mm*(2/3) / mm = ~60.5pt
    # Padding por linha = (FOTO_H/3 - 8pt) / 2
    from reportlab.lib.units import mm as _mm
    _linha_h  = FOTO_H / 3          # altura alvo por linha em pontos
    _text_h   = 8                    # altura aproximada do texto (pt)
    _pad_each = max(2, (_linha_h - _text_h) / 2)  # padding top e bottom


    def make_info_table(items, total_w, value_widths=None):
        """Linha de pares label+valor distribuídos em total_w."""
        n = len(items)
        if value_widths is None:
            val_w_each = (total_w - n * LABEL_W) / n
            value_widths = [val_w_each] * n
        cells, cws = [], []
        for (lbl, val), vw in zip(items, value_widths):
            cells += [Paragraph(lbl, S_LABEL), Paragraph(str(val), S_VALUE)]
            cws   += [LABEL_W, vw]
        t = Table([cells], colWidths=cws, rowHeights=[_linha_h])
        t.setStyle(TableStyle([
            ('VALIGN',        (0,0),(-1,-1),'MIDDLE'),
            ('ALIGN',         (0,0),(-1,-1),'LEFT'),
            ('TOPPADDING',    (0,0),(-1,-1),_pad_each),
            ('BOTTOMPADDING', (0,0),(-1,-1),_pad_each),
            ('LEFTPADDING',   (0,0),(-1,-1),3),
            ('RIGHTPADDING',  (0,0),(-1,-1),2),
        ]))
        return t


    # Larguras fixas para alinhar colunas entre as 3 linhas:
    # Col A (Instituição / Paciente / Nascimento)
    # Col B (Equipamento / ID / Idade) — alinhados na mesma coluna
    # Col C (só na linha 3: Sexo)
    # Total por linha: LABEL_W + COL_A_VAL + LABEL_W + COL_B_VAL [+ LABEL_W + COL_C_VAL]
    _COL_B_VAL = 29 * mm                             # valor col B fixo
    _COL_A_VAL = (INFO_W * 0.34) - LABEL_W           # col A reduzida a 30%
    _COL_C_VAL = INFO_W - LABEL_W - _COL_A_VAL - LABEL_W - _COL_B_VAL - LABEL_W


    # Garante que col C não seja negativa
    if _COL_C_VAL < 15 * mm:
        _COL_B_VAL = 30 * mm
        _COL_A_VAL = (INFO_W * 0.34) - LABEL_W
        _COL_C_VAL = INFO_W - LABEL_W - _COL_A_VAL - LABEL_W - _COL_B_VAL - LABEL_W


    row1 = make_info_table([("Instituição:", data["instituicao"]),
                             ("Equipamento:", data["equipamento"])],
                            INFO_W, value_widths=[_COL_A_VAL, _COL_B_VAL])
    row2 = make_info_table([("Paciente:",    data["nome_paciente"]),
                             ("ID:",          data["id_paciente"])],
                            INFO_W, value_widths=[_COL_A_VAL, _COL_B_VAL])
    row3 = make_info_table([("Nascimento:",  data["dob"]),
                             ("Idade:",       f'{data["idade"]} anos'),
                             ("Sexo:",        data["sexo"])],
                            INFO_W, value_widths=[_COL_A_VAL, _COL_B_VAL, _COL_C_VAL])


    section_header("INSTITUIÇÃO E PACIENTE")


    foto_b64 = data.get("foto_paciente")
    if foto_b64:
        from reportlab.platypus import Image as RLImage
        import base64 as _b64
        try:
            raw_b64 = foto_b64.split(",", 1)[1] if "," in foto_b64 else foto_b64
            foto_bytes = _b64.b64decode(raw_b64)


            # Corta a imagem para proporção 3:4 centralizada
            try:
                from PIL import Image as PILImage
                pil_img = PILImage.open(io.BytesIO(foto_bytes))
                iw, ih  = pil_img.size
                # Calcula crop para 3:4
                target_ratio = 3 / 4
                if iw / ih > target_ratio:
                    # Mais larga que 3:4 — corta laterais
                    new_w = int(ih * target_ratio)
                    left  = (iw - new_w) // 2
                    pil_img = pil_img.crop((left, 0, left + new_w, ih))
                else:
                    # Mais alta que 3:4 — corta topo/baixo
                    new_h = int(iw / target_ratio)
                    top   = (ih - new_h) // 2
                    pil_img = pil_img.crop((0, top, iw, top + new_h))
                out_buf = io.BytesIO()
                pil_img.save(out_buf, format="PNG")
                out_buf.seek(0)
                foto_buf = out_buf
            except Exception:
                foto_buf = io.BytesIO(foto_bytes)


            foto_img = RLImage(foto_buf, width=FOTO_W, height=FOTO_H)


            # Tabela externa: [foto | dados]
            # Foto na extrema esquerda, alinhada ao topo
            outer = Table(
                [[foto_img, [row1, row2, row3]]],
                colWidths=[FOTO_W + 2*mm, INFO_W],
            )
            outer.setStyle(TableStyle([
                ('VALIGN',        (0,0),(-1,-1),'TOP'),
                ('ALIGN',         (0,0),(0, 0),'CENTER'),
                ('LEFTPADDING',   (0,0),(-1,-1),0),
                ('RIGHTPADDING',  (0,0),(-1,-1),0),
                ('TOPPADDING',    (0,0),(-1,-1),0),
                ('BOTTOMPADDING', (0,0),(-1,-1),0),
            ]))
            story.append(outer)
        except Exception:
            story.extend([row1, row2, row3])
    else:
        story.extend([row1, row2, row3])






    # ── Bloco Plano ─────────────────────────────────────────────
    section_header("INFORMAÇÕES DO PLANO")


    # Calcula desvio total: Soma(UM_calc)/Soma(UM_TPS) - 1
    desvio_total_str = "N/A"
    try:
        soma_um_calc = sum(float(c["um_calc"]) for c in data["campos"]
                          if c.get("um_calc") not in (None, "N/A", ""))
        soma_um_tps  = sum(float(c["um"])      for c in data["campos"]
                          if c.get("um")      not in (None, "N/A", ""))
        if soma_um_tps != 0 and soma_um_calc > 0:
            desvio = (soma_um_calc / soma_um_tps - 1) * 100
            desvio_total_str = f"{desvio:.1f}%"
    except Exception:
        pass


    info_row([("Nome do Plano:",      data["nome_plano"]),
              ("Dose Total (cGy):",   data["dose_total"]),
              ("Nº Frações:",         data["fracoes"]),
              ("Data de Aprovação:",  data.get("data_aprovacao", "N/A")),
              ("Aprovado por:",       data.get("aprovado_por", "N/A") or "N/A")])




    # ── Bloco Campos ────────────────────────────────────────────
    # ── Bloco Campos — cabeçalho com Desvio Total à direita ─────
    desvio_label = f"Desvio Total: {desvio_total_str}"
    campos_header_tbl = Table(
        [[Paragraph("DETALHAMENTO DOS CAMPOS DE TRATAMENTO", S_SECTION),
          Paragraph(desvio_label, S_SECTION)]],
        colWidths=[doc.width * 0.72, doc.width * 0.28]
    )
    campos_header_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), CINZA_E),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (0, 0),  6),
        ('LEFTPADDING',   (1,0), (1, 0),  4),
        ('RIGHTPADDING',  (1,0), (1, 0),  6),
        ('ALIGN',         (1,0), (1, 0),  'RIGHT'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(campos_header_tbl)
    story.append(Spacer(1, 4))




    TH = ["Nº", "Nome\nCampo", "Feixe",
          "En.\n(MeV)", "Filtro", "Técnica",
          "X1\n(cm)", "X2\n(cm)", "X\n(cm)",
          "Y1\n(cm)", "Y2\n(cm)", "Y\n(cm)",
          "Dose\n(cGy)", "Prof.\n(cm)", "TMR", "TMRw", "Scp",
          "UM\n(TPS)", "UM\n(Calc.)", "Δ%"]


    W = doc.width
    col_w = [
        5*mm,   # Nº
        20*mm,  # Nome
        12*mm,  # Feixe
        8*mm,   # Energia
        10*mm,  # Filtro
        12*mm,  # Técnica
        8*mm,   # X1
        8*mm,   # X2
        8*mm,   # X(cm)
        8*mm,   # Y1
        8*mm,   # Y2
        8*mm,   # Y(cm)
        10*mm,  # Dose
        9*mm,   # Prof.
        10*mm,  # TMR
        10*mm,  # TMRw
        10*mm,  # Scp
        10*mm,  # UM TPS
        10*mm,  # UM Calc.
        10*mm,  # Δ%
    ]
    scale = W / sum(col_w)
    col_w = [c * scale for c in col_w]


    header_row = [Paragraph(h, S_TH) for h in TH]
    table_data = [header_row]


    GREEN  = colors.HexColor("#1e6641")
    YELLOW = colors.HexColor("#7a5f00")
    RED    = colors.HexColor("#8b0000")
    BG_G   = colors.HexColor("#e6f4ec")
    BG_Y   = colors.HexColor("#fff3cd")
    BG_R   = colors.HexColor("#fde8e8")


    diff_row_styles = []


    for i, c in enumerate(data["campos"]):
        diff_str = c.get("diff_pct", "N/A") or "N/A"
        try:
            dv = abs(float(diff_str))
            d_color = GREEN if dv <= 3 else YELLOW if dv <= 5 else RED
            d_bg    = BG_G  if dv <= 3 else BG_Y   if dv <= 5 else BG_R
            diff_display = f"{diff_str}%"
        except Exception:
            d_color = colors.HexColor("#555555")
            d_bg    = colors.white
            diff_display = str(diff_str) if diff_str else "N/A"


        row_idx = i + 1
        diff_col_idx = len(TH) - 1
        diff_row_styles.append(('TEXTCOLOR',  (diff_col_idx, row_idx), (diff_col_idx, row_idx), d_color))
        diff_row_styles.append(('BACKGROUND', (diff_col_idx, row_idx), (diff_col_idx, row_idx), d_bg))
        diff_row_styles.append(('FONTNAME',   (diff_col_idx, row_idx), (diff_col_idx, row_idx), 'Helvetica-Bold'))


        def s(val, default="N/A"):
            """Converte qualquer valor para string segura para Paragraph."""
            if val is None or val == "" or val is False:
                return default
            return str(val)


        row = [
            Paragraph(s(c.get("numero")),         S_TD),
            Paragraph(s(c.get("nome")),            S_TD),
            Paragraph(s(c.get("feixe")),           S_TD),
            Paragraph(s(c.get("energia")),         S_TD),
            Paragraph(s(c.get("filtro"), "—"),     S_TD),
            Paragraph(s(c.get("tecnica")),         S_TD),
            Paragraph(s(c.get("campo_x1")),        S_TD),
            Paragraph(s(c.get("campo_x2")),        S_TD),
            Paragraph(s(c.get("campo_x_cm")),      S_TD),
            Paragraph(s(c.get("campo_y1")),        S_TD),
            Paragraph(s(c.get("campo_y2")),        S_TD),
            Paragraph(s(c.get("campo_y_cm")),      S_TD),
            Paragraph(s(c.get("dose")),            S_TD),
            Paragraph(s(c.get("profundidade")),    S_TD),
            Paragraph(s(c.get("tmr")),             S_TD),
            Paragraph(s(c.get("tmrw")),            S_TD),
            Paragraph(s(c.get("scp")),             S_TD),
            Paragraph(s(c.get("um")),              S_TD),
            Paragraph(s(c.get("um_calc")),         S_TD),
            Paragraph(diff_display,                S_TD),
        ]
        table_data.append(row)


    ct = Table(table_data, colWidths=col_w, repeatRows=1)
    base_style = [
        ('BACKGROUND',    (0, 0), (-1, 0),  CINZA_E),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_L]),
        ('GRID',          (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),   # centraliza tudo
        ('ALIGN',         (0, 1), (-1, -1), 'CENTER'),   # garante dados centralizados
    ]
    ct.setStyle(TableStyle(base_style + diff_row_styles))
    story.append(ct)
    story.append(Spacer(1, 10))


    # ── Rodapé ───────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_M, spaceAfter=4))
    usuario = data.get("usuario", "N/A")
    exec_dt = data.get("exec_datetime", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    story.append(Paragraph(
        f"Data de execução: {exec_dt} &nbsp;|&nbsp; Usuário: {usuario} &nbsp;|&nbsp; "
        "Relatório gerado automaticamente — Sistema RT Plan Viewer",
        S_FOOT
    ))


    doc.build(story)
    buf.seek(0)
    return buf




# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)




# ── Tabelas consultivas ────────────────────────────────────────


@app.route("/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/config", methods=["POST"])
def set_config():
    data = request.get_json()
    cfg = load_config()
    if "equipamento_fabricante" in data:
        cfg["equipamento_fabricante"] = data["equipamento_fabricante"]
    if "fw_energia" in data and "fw_valor" in data:
        try:
            energia_key = str(float(str(data["fw_energia"]).replace(",", ".")))
            fw_val      = float(str(data["fw_valor"]).replace(",", "."))
            if "fw" not in cfg or not isinstance(cfg["fw"], dict):
                cfg["fw"] = {}
            cfg["fw"][energia_key] = fw_val
        except Exception:
            pass
    if "fw_delete" in data:
        try:
            energia_key = str(float(str(data["fw_delete"]).replace(",", ".")))
            cfg.get("fw", {}).pop(energia_key, None)
        except Exception:
            pass
    if "fd_energia" in data and "fd_valor" in data:
        try:
            energia_key = str(float(str(data["fd_energia"]).replace(",", ".")))
            fd_val      = float(str(data["fd_valor"]).replace(",", "."))
            if "fd" not in cfg or not isinstance(cfg["fd"], dict):
                cfg["fd"] = {}
            cfg["fd"][energia_key] = fd_val
        except Exception:
            pass
    if "fd_delete" in data:
        try:
            energia_key = str(float(str(data["fd_delete"]).replace(",", ".")))
            cfg.get("fd", {}).pop(energia_key, None)
        except Exception:
            pass
    save_config(cfg)
    return jsonify({"ok": True, "config": cfg})


@app.route("/logo", methods=["GET"])
def get_logo():
    if os.path.exists(LOGO_PATH):
        ext = LOGO_PATH.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
        return send_file(LOGO_PATH, mimetype=mime)
    return "", 404


@app.route("/logo/upload", methods=["POST"])
def upload_logo():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    f = request.files["file"]
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ("png", "jpg", "jpeg"):
        return jsonify({"error": "Formato inválido. Use PNG, JPG ou JPEG."}), 400
    # Salva sempre como PNG para simplicidade
    raw = f.read()
    # Detecta extensão real e salva com ela
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"logo.{ext}")
    # Remove logo anterior com qualquer extensão
    for e in ("png", "jpg", "jpeg"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"logo.{e}")
        if os.path.exists(p):
            os.remove(p)
    with open(logo_path, "wb") as fp:
        fp.write(raw)
    # Atualiza LOGO_PATH global
    global LOGO_PATH
    LOGO_PATH = logo_path
    return jsonify({"ok": True, "filename": f.filename})


@app.route("/logo/delete", methods=["POST"])
def delete_logo():
    global LOGO_PATH
    for e in ("png", "jpg", "jpeg"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"logo.{e}")
        if os.path.exists(p):
            os.remove(p)
    LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    return jsonify({"ok": True})


@app.route("/tables", methods=["GET"])
def list_tables():
    return jsonify(load_tables_index())




@app.route("/tables/upload", methods=["POST"])
def upload_table():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    f       = request.files["file"]
    category = request.form.get("category", "TMR")
    energia  = request.form.get("energia", "")
    label    = request.form.get("label", f.filename)


    raw = f.read()
    try:
        if category == "Scp":
            table_data = parse_scp_file(raw, f.filename)
            n_rows = len(table_data["fields"])
            n_cols = 1
        else:  # TMR ou TMRw — mesmo formato 2D
            table_data = parse_table_file(raw, f.filename)
            n_rows = len(table_data["rows"])
            n_cols = len(table_data["cols"])
    except Exception as e:
        return jsonify({"error": str(e)}), 400


    tid      = str(uuid.uuid4())[:8]
    json_name = f"{tid}.json"
    fpath     = os.path.join(TABLES_DIR, json_name)
    with open(fpath, "w", encoding="utf-8") as fp:
        json.dump(table_data, fp)


    idx = load_tables_index()
    idx[tid] = {
        "name":        label,
        "category":    category,
        "energia":     energia,
        "filename":    json_name,
        "original":    f.filename,
        "uploaded_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_rows":      n_rows,
        "n_cols":      n_cols,
    }
    save_tables_index(idx)
    return jsonify({"ok": True, "id": tid, "meta": idx[tid]})




@app.route("/tables/<tid>", methods=["DELETE"])
def delete_table(tid):
    idx = load_tables_index()
    if tid not in idx:
        return jsonify({"error": "Não encontrado"}), 404
    fpath = os.path.join(TABLES_DIR, idx[tid]["filename"])
    if os.path.exists(fpath):
        os.remove(fpath)
    del idx[tid]
    save_tables_index(idx)
    return jsonify({"ok": True})




@app.route("/parse", methods=["POST"])
def parse_route():
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Nome de arquivo inválido"}), 400
    try:
        data = parse_dicom(f.read())
        # Append system info
        data["usuario"] = getpass.getuser()
        data["exec_datetime"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return jsonify(data)
    except ImportError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Erro ao ler arquivo DICOM: {str(e)}"}), 500




@app.route("/recalc", methods=["POST"])
def recalc_route():
    """
    Recebe parsedData + {bnum: angulo} e recalcula UM(calc) para campos com filtro.
    Fórmula: UM = k*(Dose/(TMRw*Scp*FW*FD)) + (1-k)*[alpha*Σ_i_ímpares + beta*Σ_j_todos]
    """
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Dados inválidos"}), 400


    angulos = payload.get("angulos", {})
    campos  = payload.get("campos", [])


    def soma_cps_from_dict(c_dict, dose_f, fd_f, usar_impares=True):
        """
        Reconstrói o somatório por CP usando segmentos_cp serializado no parse.
        """
        segs = c_dict.get("segmentos_cp")
        if not segs:
            return None
        energia = c_dict.get("energia", "N/A")
        soma = 0.0
        for seg in segs:
            cp_idx = seg.get("cp_idx", -1)
            if usar_impares and cp_idx % 2 == 0:
                continue
            if not usar_impares and cp_idx == 0:
                continue
            dMw   = seg.get("dMw", 0)
            xi    = seg.get("xi")
            yi    = seg.get("yi")
            depth = seg.get("depth_cm")
            if dMw <= 0 or xi is None or yi is None or depth is None:
                return None
            tmr_cp = get_tmr_for_beam(energia, xi, yi, depth)
            scp_cp = get_scp_for_beam(energia, xi, yi)
            if tmr_cp is None or scp_cp is None or tmr_cp * scp_cp * fd_f == 0:
                return None
            soma += dMw * dose_f / (tmr_cp * scp_cp * fd_f)
        return soma


    for c in campos:
        if not c.get("filtro_presente"):
            continue
        bnum   = c["numero"]
        angulo = angulos.get(str(bnum))
        if angulo is None:
            continue
        try:
            angulo_f  = float(angulo)
            k_val     = math.tan(angulo_f * math.pi / 180) / math.tan(60 * math.pi / 180)
            c["angulo_filtro"] = angulo_f
            c["filtro"] = f"{angulo_f:.0f}°"


            energia  = c.get("energia", "N/A")
            dose_f   = float(c["dose"])
            tmrw_val = c.get("tmrw", "N/A")
            scp_val  = c.get("scp",  "N/A")
            um_campo = c.get("um",   "N/A")
            fw       = get_fw_for_energia(energia)
            fd       = get_fd_for_energia(energia)
            alpha    = c.get("alpha", 1)
            beta     = c.get("beta",  0)


            if fd is None:
                continue
            fd_f = float(fd)


            # Termo 1: k * Dose / (TMRw * Scp * FW * FD)
            termo1 = 0.0
            if k_val > 0 and tmrw_val not in ("N/A", None) and scp_val not in ("N/A", None) and fw is not None:
                tmrw_f = float(tmrw_val)
                scp_f  = float(scp_val)
                fw_f   = float(fw)
                if tmrw_f * scp_f * fw_f * fd_f != 0:
                    termo1 = k_val * dose_f / (tmrw_f * scp_f * fw_f * fd_f)


            # Termo 2: (1-k) * [alpha*Σ_i + beta*Σ_j]
            soma_i = soma_cps_from_dict(c, dose_f, fd_f, usar_impares=True)  if alpha == 1 else 0.0
            soma_j = soma_cps_from_dict(c, dose_f, fd_f, usar_impares=False) if beta  == 1 else 0.0


            # Se não temos segmentos_cp, fallback para fórmula simples com TMR do campo
            if soma_i is None and soma_j is None:
                tmr_f = float(c["tmr"]) if c.get("tmr") not in ("N/A", None) else None
                scp_f = float(scp_val)  if scp_val not in ("N/A", None) else None
                if tmr_f and scp_f and tmr_f * scp_f * fd_f != 0:
                    soma_i = dose_f / (tmr_f * scp_f * fd_f) if alpha == 1 else None
                    soma_j = dose_f / (tmr_f * scp_f * fd_f) if beta  == 1 else None


            termo2 = (1 - k_val) * ((soma_i or 0.0) + (soma_j or 0.0))
            um_calc = termo1 + termo2


            if um_calc > 0:
                c["um_calc"] = f"{um_calc:.1f}"
                if um_campo not in ("N/A", None):
                    um_tps_f = float(um_campo)
                    if um_tps_f != 0:
                        diff = (um_calc - um_tps_f) / um_tps_f * 100
                        c["diff_pct"] = f"{diff:.1f}"
        except Exception:
            continue


    return jsonify({"ok": True, "campos": campos})




@app.route("/pdf", methods=["POST"])
def pdf_route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Dados inválidos"}), 400
    try:
        pdf_buf = generate_pdf(data)
        id_pac    = data.get('id_paciente', 'ID').replace(' ', '_')
        nome_pac  = data.get('nome_paciente', 'paciente').replace(' ', '_')
        hoje      = datetime.now().strftime('%d-%m-%Y')
        nome_plan = data.get('nome_plano', 'plano').replace(' ', '_')
        filename  = f"{id_pac} {nome_pac} {hoje} {nome_plan}.pdf"
        # Remove caracteres inválidos para nome de arquivo
        import re
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar PDF: {str(e)}"}), 500




# ─────────────────────────────────────────────────────────────
# HTML TEMPLATE (inline)
# ─────────────────────────────────────────────────────────────


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RT Plan Viewer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,600;0,700;1,300&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }


:root {
  --bg:      #f5f4f0;
  --surface: #ffffff;
  --border:  #d0cfc9;
  --text:    #1a1a18;
  --muted:   #6b6b65;
  --accent:  #1a1a18;
  --row-alt: #f9f8f5;
  --tag-bg:  #e8e7e2;
  --green:   #1e6641;
  --shadow:  0 1px 3px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.06);
}


body {
  font-family: 'IBM Plex Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.5;
}


/* ── Header ── */
.app-header {
  background: var(--accent);
  color: #fff;
  padding: 18px 32px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.app-header .logo {
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: .04em;
  color: #fff;
}
.app-header .sub {
  font-size: 11px;
  color: rgba(255,255,255,.55);
  font-weight: 300;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.header-sep { flex: 1; }


/* ── Layout ── */
.container {
  max-width: 1240px;
  margin: 0 auto;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}


/* ── Upload card ── */
.upload-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow);
  padding: 28px 32px;
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}


.drop-zone {
  border: 2px dashed var(--border);
  border-radius: 6px;
  padding: 22px 36px;
  text-align: center;
  cursor: pointer;
  transition: border-color .2s, background .2s;
  min-width: 280px;
  flex: 1;
  position: relative;
}
.drop-zone:hover, .drop-zone.over {
  border-color: var(--accent);
  background: var(--row-alt);
}
.drop-zone input[type=file] {
  position: absolute; inset: 0;
  opacity: 0; cursor: pointer;
}
.drop-zone .icon { font-size: 28px; margin-bottom: 6px; }
.drop-zone .hint {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
}


.btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px 20px;
  border-radius: 4px;
  border: 1px solid transparent;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity .15s, transform .1s;
}
.btn:active { transform: scale(.98); }
.btn-primary {
  background: var(--accent);
  color: #fff;
}
.btn-primary:hover { opacity: .85; }
.btn-outline {
  background: transparent;
  border-color: var(--border);
  color: var(--text);
}
.btn-outline:hover { background: var(--row-alt); }
.btn-green {
  background: var(--green);
  color: #fff;
}
.btn-green:hover { opacity: .85; }
.btn:disabled { opacity: .4; cursor: not-allowed; }


/* ── Status bar ── */
#status-bar {
  display: none;
  padding: 10px 16px;
  border-radius: 4px;
  font-size: 12px;
  font-family: 'IBM Plex Mono', monospace;
  background: #fff3cd;
  border: 1px solid #ffe89b;
  color: #7a5f00;
}
#status-bar.error {
  background: #fde8e8;
  border-color: #f5b7b7;
  color: #8b0000;
}
#status-bar.success {
  background: #e6f4ec;
  border-color: #9ed8b4;
  color: #1e6641;
}


/* ── Result sections ── */
#result { display: none; flex-direction: column; gap: 16px; }


.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow);
  overflow: hidden;
}
.card-header {
  background: var(--accent);
  color: #fff;
  padding: 9px 18px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-body { padding: 18px 20px; }


/* ── Info grid ── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px 20px;
}
.info-item label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 2px;
}
.info-item .val {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  font-family: 'IBM Plex Mono', monospace;
}
.info-item .val.wide {
  font-size: 13px;
  font-family: 'IBM Plex Sans', sans-serif;
}


/* ── Fields table ── */
.table-wrap { overflow-x: auto; }
table.fields-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.fields-table thead tr {
  background: var(--tag-bg);
}
.fields-table th {
  padding: 9px 10px;
  text-align: left;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 2px solid var(--border);
  white-space: nowrap;
}
.fields-table td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--border);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  vertical-align: middle;
}
.fields-table tbody tr:nth-child(even) { background: var(--row-alt); }
.fields-table tbody tr:hover { background: #eeecea; }
.fields-table td:first-child {
  font-weight: 600;
  width: 44px;
  text-align: center;
}


/* ── Action bar ── */
.action-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}


/* ── Spinner ── */
.spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }


/* ── Filename tag ── */
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--tag-bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-family: 'IBM Plex Mono', monospace;
  color: var(--text);
}


/* ── Config Modal ── */
.modal-overlay {
  display: none;
  position: fixed; inset: 0;
  background: rgba(0,0,0,.45);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 40px rgba(0,0,0,.2);
  width: min(720px, 94vw);
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.modal-header {
  background: var(--accent);
  color: #fff;
  padding: 14px 20px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: .08em;
  display: flex;
  align-items: center;
  gap: 10px;
}
.modal-header .close-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: rgba(255,255,255,.7);
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
}
.modal-header .close-btn:hover { color: #fff; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 10px;
  align-items: center;
}
.upload-form {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
  align-items: end;
}
.form-group label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-group input, .form-group select {
  width: 100%;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 12px;
  background: var(--bg);
  color: var(--text);
}
.form-group input:focus, .form-group select:focus {
  outline: none;
  border-color: var(--accent);
}
.tables-list { margin-top: 8px; }
.table-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  margin-bottom: 6px;
  background: var(--row-alt);
  font-size: 12px;
}
.table-row .t-name { font-weight: 600; flex: 1; }
.table-row .t-meta { color: var(--muted); font-family: 'IBM Plex Mono', monospace; font-size: 11px; }
.table-row .t-del {
  background: none; border: none;
  color: #b00; cursor: pointer; font-size: 14px; padding: 2px 6px;
  border-radius: 3px;
}
.table-row .t-del:hover { background: #fde8e8; }
.empty-tables {
  text-align: center;
  padding: 24px;
  color: var(--muted);
  font-size: 13px;
  border: 2px dashed var(--border);
  border-radius: 6px;
}


@media (max-width: 600px) {
  .app-header { padding: 14px 16px; }
  .container   { padding: 16px 12px; }
  .upload-card { padding: 18px 16px; }
  .upload-form { grid-template-columns: 1fr; }
}
</style>
</head>
<body>


<header class="app-header">
  <div>
    <div class="logo">RT Plan Viewer</div>
    <div class="sub">DICOM Radiotherapy Plan Analyzer</div>
  </div>
  <div class="header-sep"></div>
  <button class="btn btn-outline" id="btnConfig" style="border-color:rgba(255,255,255,.3);color:#fff;">
    ⚙️ Configurações
  </button>
  &nbsp;
  <div style="font-size:11px;color:rgba(255,255,255,.4);font-family:'IBM Plex Mono',monospace;">v1.0</div>
</header>


<div class="container">


<!-- ── Config Modal ─────────────────────────────────────── -->
<div class="modal-overlay" id="configModal">
  <div class="modal">
    <div class="modal-header">
      ⚙️ CONFIGURAÇÕES — TABELAS CONSULTIVAS
      <button class="close-btn" id="btnCloseModal">✕</button>
    </div>
    <div class="modal-body">


      <div style="margin-bottom:16px;">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px;">Logo da Instituição</div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">
          Aparecerá no cabeçalho do relatório PDF. Formatos: JPG, JPEG, PNG.
        </div>
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
          <img id="logoPreview" src="/logo" onerror="this.style.display='none'"
               style="height:48px;max-width:120px;object-fit:contain;border:1px solid var(--border);border-radius:4px;padding:4px;">
          <div style="display:flex;gap:8px;align-items:center;">
            <input type="file" id="cfgLogoFile" accept=".jpg,.jpeg,.png"
                   style="font-size:12px;font-family:'IBM Plex Mono',monospace;">
            <button class="btn btn-outline" id="btnUploadLogo" style="height:34px;">⬆ Enviar</button>
            <button class="btn btn-outline" id="btnDeleteLogo"
                    style="height:34px;color:#8b0000;border-color:#f5b7b7;">🗑 Remover</button>
          </div>
        </div>
        <div id="cfgLogoStatus" style="display:none;margin-top:8px;padding:7px 12px;border-radius:4px;font-size:12px;font-family:'IBM Plex Mono',monospace;"></div>
        <hr style="border:none;border-top:1px solid var(--border);margin:14px 0;">
      </div>


      <div style="margin-bottom:16px;">
        <div style="font-weight:700;font-size:13px;margin-bottom:8px;">Equipamento / Fabricante</div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">
          Esta configuração é usada para ativar a lógica de filtro virtual (Elekta W60).
        </div>
        <div class="upload-form" style="grid-template-columns:1fr 1fr 1fr;">
          <div class="form-group">
            <label>Fabricante</label>
            <select id="cfgFabricante">
              <option value="">— selecionar —</option>
              <option value="ELEKTA">ELEKTA</option>
              <option value="VARIAN">VARIAN</option>
            </select>
          </div>
          <div class="form-group" style="display:flex;align-items:flex-end;">
            <button class="btn btn-primary" id="btnSaveFabricante" style="width:100%;">
              💾 Salvar fabricante
            </button>
          </div>
        </div>
        <div id="cfgConfigStatus" style="display:none;margin-bottom:8px;padding:7px 12px;border-radius:4px;font-size:12px;font-family:'IBM Plex Mono',monospace;"></div>


        <div style="margin-top:12px;">
          <div style="font-weight:600;font-size:12px;margin-bottom:8px;">Fatores FW por energia</div>
          <div class="upload-form" style="grid-template-columns:1fr 1fr auto;align-items:end;gap:8px;">
            <div class="form-group">
              <label>Energia (MeV)</label>
              <input type="number" step="0.5" id="cfgFWEnergia" placeholder="ex: 6">
            </div>
            <div class="form-group">
              <label>Valor FW</label>
              <input type="number" step="0.0001" id="cfgFWValor" placeholder="ex: 0.7521">
            </div>
            <button class="btn btn-outline" id="btnAddFW" style="height:36px;white-space:nowrap;">
              + Adicionar
            </button>
          </div>
          <div id="fwList" style="margin-top:8px;"></div>
        </div>


        <div style="margin-top:14px;">
          <div style="font-weight:600;font-size:12px;margin-bottom:8px;">Fatores FD (Fator Distância) por energia</div>
          <div class="upload-form" style="grid-template-columns:1fr 1fr auto;align-items:end;gap:8px;">
            <div class="form-group">
              <label>Energia (MeV)</label>
              <input type="number" step="0.5" id="cfgFDEnergia" placeholder="ex: 6">
            </div>
            <div class="form-group">
              <label>Valor FD</label>
              <input type="number" step="0.0001" id="cfgFDValor" placeholder="ex: 1.0200">
            </div>
            <button class="btn btn-outline" id="btnAddFD" style="height:36px;white-space:nowrap;">
              + Adicionar
            </button>
          </div>
          <div id="fdList" style="margin-top:8px;"></div>
        </div>


        <hr style="border:none;border-top:1px solid var(--border);margin:16px 0;">
      </div>


      <div style="margin-bottom:12px;">
        <div style="font-weight:700;font-size:13px;margin-bottom:4px;">Adicionar nova tabela</div>
        <div style="font-size:12px;color:var(--muted);margin-bottom:10px;">
          Formatos aceitos: <b>.xlsx</b>, <b>.xls</b>, <b>.csv</b> —
          Cabeçalho da primeira linha = tamanhos de campo (LxL); primeira coluna = profundidade (cm).
        </div>
      </div>


      <div class="upload-form">
        <div class="form-group">
          <label>Categoria</label>
          <select id="cfgCategory">
            <option value="TMR">TMR</option>
            <option value="TMRw">TMRw (com filtro virtual)</option>
            <option value="Scp">Scp</option>
          </select>
        </div>
        <div class="form-group">
          <label>Energia (MeV)</label>
          <input type="number" step="0.5" id="cfgEnergia" placeholder="ex: 6">
        </div>
        <div class="form-group">
          <label>Rótulo / descrição</label>
          <input type="text" id="cfgLabel" placeholder="ex: TMR 6MV Clínico">
        </div>
        <div class="form-group" style="grid-column:1/-1;">
          <label>Arquivo</label>
          <input type="file" id="cfgFile" accept=".xlsx,.xls,.csv">
        </div>
        <div class="form-group" style="grid-column:1/-1;">
          <button class="btn btn-primary" id="btnUploadTable" style="width:100%;">
            ⬆ Fazer upload da tabela
          </button>
        </div>
      </div>


      <div id="cfgStatus" style="display:none;margin-bottom:12px;padding:8px 12px;border-radius:4px;font-size:12px;font-family:'IBM Plex Mono',monospace;"></div>


      <div style="font-weight:700;font-size:13px;margin-bottom:8px;">Tabelas cadastradas</div>
      <div id="tablesList" class="tables-list">
        <div class="empty-tables">Nenhuma tabela cadastrada.</div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" id="btnCloseModal2">Fechar</button>
    </div>
  </div>
</div>


<!-- ── Modal Seleção de Fabricante ──────────────────────── -->
<div class="modal-overlay" id="equipModal">
  <div class="modal" style="width:min(440px,94vw);">
    <div class="modal-header">⚙️ IDENTIFICAÇÃO DO EQUIPAMENTO</div>
    <div class="modal-body" style="padding:28px 24px;">
      <p style="font-size:13px;margin-bottom:18px;line-height:1.6;color:var(--text);">
        Selecione o fabricante do acelerador antes de prosseguir.<br>
        Esta escolha determina o modelo de cálculo de UM utilizado.
      </p>
      <div class="form-group" style="margin-bottom:20px;">
        <label>Fabricante</label>
        <select id="modalFabricante" style="font-size:14px;padding:10px;">
          <option value="">— selecionar —</option>
          <option value="ELEKTA">ELEKTA</option>
          <option value="VARIAN">VARIAN (em desenvolvimento)</option>
        </select>
      </div>
      <button class="btn btn-primary" id="btnConfirmEquip" style="width:100%;padding:12px;font-size:14px;" disabled>
        ✓ Confirmar e Analisar
      </button>
    </div>
  </div>
</div>


<!-- ── Modal Ângulo de Filtro ────────────────────────────── -->
<div class="modal-overlay" id="filtroModal">
  <div class="modal" style="width:min(500px,94vw);">
    <div class="modal-header">🔆 ÂNGULO DO FILTRO VIRTUAL</div>
    <div class="modal-body" style="padding:24px;">
      <p style="font-size:13px;margin-bottom:16px;line-height:1.6;color:var(--text);">
        Os campos abaixo utilizam filtro virtual.<br>
        Informe o <strong>ângulo real</strong> de cada filtro para calcular a UM.
      </p>
      <div id="filtroInputs" style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px;"></div>
      <button class="btn btn-primary" id="btnConfirmFiltro" style="width:100%;padding:12px;font-size:14px;">
        ✓ Confirmar ângulos e calcular
      </button>
    </div>
  </div>
</div>


  <!-- Upload -->
  <div class="upload-card">
    <div class="drop-zone" id="dropZone">
      <input type="file" id="fileInput" accept=".dcm,.DCM,application/dicom">
      <div class="icon">📂</div>
      <div style="font-weight:600;font-size:13px;">Selecionar arquivo DICOM</div>
      <div class="hint">Arraste e solte ou clique para escolher<br>Formato: .dcm (RT Plan)</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:10px;min-width:160px;">
      <button class="btn btn-primary" id="btnParse" disabled>
        ⚡ Analisar DICOM
      </button>
      <button class="btn btn-green" id="btnPdf" disabled>
        📄 Exportar PDF
      </button>
      <button class="btn btn-outline" id="btnClear" disabled>
        ✕ Limpar
      </button>
    </div>
    <div style="display:flex;flex-direction:column;gap:6px;min-width:130px;">
      <div style="font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);">
        Foto do Paciente
      </div>
      <div id="fotoPreviewWrap" style="width:90px;height:90px;border:2px dashed var(--border);border-radius:6px;
           display:flex;align-items:center;justify-content:center;overflow:hidden;background:var(--row-alt);cursor:pointer;"
           onclick="document.getElementById('fotoInput').click()">
        <img id="fotoPreview" style="display:none;width:100%;height:100%;object-fit:cover;">
        <span id="fotoIcon" style="font-size:26px;">👤</span>
      </div>
      <input type="file" id="fotoInput" accept=".jpg,.jpeg,.png" style="display:none;">
      <button class="btn btn-outline" id="btnRemoveFoto" style="display:none;font-size:11px;padding:4px 8px;">✕ Remover foto</button>
    </div>
  </div>


  <!-- Status -->
  <div id="status-bar"></div>


  <!-- Results -->
  <div id="result">


    <!-- Instituição / Paciente -->
    <div class="card">
      <div class="card-header">🏥 Instituição &amp; Paciente</div>
      <div class="card-body">
        <div class="info-grid">
          <div class="info-item"><label>Instituição</label><div class="val wide" id="r-inst">—</div></div>
          <div class="info-item"><label>Equipamento</label><div class="val wide" id="r-equip">—</div></div>
          <div class="info-item"><label>Nome do Paciente</label><div class="val wide" id="r-nome">—</div></div>
          <div class="info-item"><label>ID do Paciente</label><div class="val" id="r-id">—</div></div>
          <div class="info-item"><label>Sexo</label><div class="val" id="r-sexo">—</div></div>
          <div class="info-item"><label>Data de Nascimento</label><div class="val" id="r-dob">—</div></div>
          <div class="info-item"><label>Idade</label><div class="val" id="r-idade">—</div></div>
        </div>
      </div>
    </div>


    <!-- Plano -->
    <div class="card">
      <div class="card-header">📋 Informações do Plano</div>
      <div class="card-body">
        <div class="info-grid">
          <div class="info-item"><label>Nome do Plano</label><div class="val wide" id="r-plano">—</div></div>
          <div class="info-item"><label>Dose Total (cGy)</label><div class="val" id="r-dose">—</div></div>
          <div class="info-item"><label>Número de Frações</label><div class="val" id="r-frac">—</div></div>
          <div class="info-item"><label>Data de Aprovação</label><div class="val" id="r-aprov">—</div></div>
          <div class="info-item"><label>Aprovado por</label><div class="val wide" id="r-aprovpor">—</div></div>
        </div>
      </div>
    </div>


    <!-- Campos -->
    <div class="card">
      <div class="card-header">☢️ Campos de Tratamento <span id="r-nfields" style="opacity:.6;font-weight:400;margin-left:8px;"></span>
        <span class="header-sep"></span>
        <span id="r-desvio-badge" style="display:none;font-size:11px;font-weight:700;padding:2px 10px;border-radius:3px;margin-left:auto;"></span>
      </div>
      <div class="card-body" style="padding:0;">
        <div class="table-wrap">
          <table class="fields-table">
            <thead>
              <tr>
                <th>Nº</th>
                <th>Nome do Campo</th>
                <th>Feixe</th>
                <th>Energia (MeV)</th>
                <th>Filtro</th>
                <th>Técnica</th>
                <th>X1 (cm)</th>
                <th>X2 (cm)</th>
                <th>X (cm)</th>
                <th>Y1 (cm)</th>
                <th>Y2 (cm)</th>
                <th>Y (cm)</th>
                <th>Dose (cGy)</th>
                <th>Prof. (cm)</th>
                <th>TMR</th>
                <th>TMRw</th>
                <th>Scp</th>
                <th>UM (TPS)</th>
                <th>UM (Calc.)</th>
                <th>Δ%</th>
              </tr>
            </thead>
            <tbody id="r-campos"></tbody>
          </table>
        </div>
      </div>
    </div>


    <!-- Actions -->
    <div class="action-bar" id="bottom-actions" style="justify-content:flex-end;">
      <button class="btn btn-green" id="btnPdf2">📄 Exportar Relatório PDF</button>
    </div>


  </div><!-- /result -->


</div><!-- /container -->


<script>
let parsedData = null;
const fileInput  = document.getElementById('fileInput');
const dropZone   = document.getElementById('dropZone');
const btnParse   = document.getElementById('btnParse');
const btnPdf     = document.getElementById('btnPdf');
const btnPdf2    = document.getElementById('btnPdf2');
const btnClear   = document.getElementById('btnClear');
const statusBar  = document.getElementById('status-bar');
const resultDiv  = document.getElementById('result');


// ── File selection ────────────────────────────────────────────
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) onFileSelected(fileInput.files[0]);
});


dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('over'); });
dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('over');
  if (e.dataTransfer.files[0]) onFileSelected(e.dataTransfer.files[0]);
});


function onFileSelected(file) {
  dropZone.querySelector('div:nth-child(2)').textContent = '';
  const hintEl = dropZone.querySelector('.hint');
  hintEl.innerHTML = `<span class="file-tag">📎 ${file.name}</span>`;
  btnParse.disabled = false;
  btnClear.disabled = false;
  hideStatus();
  resetResult();
}


// ── Equipment Modal ───────────────────────────────────────────
const equipModal   = document.getElementById('equipModal');
const modalFab     = document.getElementById('modalFabricante');
const btnConfirm   = document.getElementById('btnConfirmEquip');
let   pendingFile  = null;


modalFab.addEventListener('change', () => {
  btnConfirm.disabled = !modalFab.value;
});


btnParse.addEventListener('click', () => {
  const file = fileInput.files[0];
  if (!file) return;
  pendingFile = file;
  modalFab.value = '';
  btnConfirm.disabled = true;
  equipModal.classList.add('open');
});


btnConfirm.addEventListener('click', async () => {
  equipModal.classList.remove('open');
  await doParse(pendingFile, modalFab.value);
});


async function doParse(file, fabricante) {
  btnParse.innerHTML = '<span class="spinner"></span> Analisando...';
  btnParse.disabled = true;
  showStatus('Lendo arquivo DICOM...', 'loading');


  const fd = new FormData();
  fd.append('file', file);
  fd.append('fabricante', fabricante);


  try {
    const res  = await fetch('/parse', { method: 'POST', body: fd });
    const json = await res.json();


    if (!res.ok || json.error) {
      showStatus('Erro: ' + (json.error || 'Falha ao processar arquivo'), 'error');
      btnParse.innerHTML = '⚡ Analisar DICOM';
      btnParse.disabled  = false;
      return;
    }


    parsedData = json;
    populateResult(json);
    // Debug: mostra motivo do N/A no console
    json.campos.forEach(c => {
      if (c.um_calc === 'N/A') {
        console.warn(`[UM_CALC N/A] Campo ${c.nome}: ${c.um_calc_debug || 'sem debug'}`);
      }
    });
    resultDiv.style.display = 'flex';
    btnPdf.disabled  = false;
    btnParse.innerHTML = '✓ Analisado';
    showStatus(`Arquivo DICOM processado com sucesso — ${json.campos.length} campo(s) encontrado(s)`, 'success');
    // Verifica se há campos com filtro aguardando ângulo do usuário
    const camposComFiltro = json.campos.filter(c => c.filtro_presente);
    if (camposComFiltro.length > 0) {
      showFiltroModal(camposComFiltro);
    }


    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });


  } catch (err) {
    showStatus('Erro de conexão: ' + err.message, 'error');
    btnParse.innerHTML = '⚡ Analisar DICOM';
    btnParse.disabled  = false;
  }
}


// ── PDF export ────────────────────────────────────────────────
async function exportPdf() {
  if (!parsedData) return;
  showStatus('Gerando PDF...', 'loading');
  try {
    const payload = Object.assign({}, parsedData, { foto_paciente: fotoBase64 || null });
    const res = await fetch('/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const j = await res.json();
      showStatus('Erro ao gerar PDF: ' + (j.error || ''), 'error');
      return;
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    const hoje    = new Date().toLocaleDateString('pt-BR').split('/').join('-'); // dd-mm-aaaa
    const id_pac  = (parsedData.id_paciente  || 'ID').replace(/\s+/g,'_');
    const nome    = (parsedData.nome_paciente || 'paciente').replace(/\s+/g,'_');
    const plano   = (parsedData.nome_plano    || 'plano').replace(/[\s/\\*?:"<>|]+/g,'_');
    a.download = `${id_pac} ${nome} ${hoje} ${plano}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    showStatus('PDF exportado com sucesso!', 'success');
  } catch (err) {
    showStatus('Erro: ' + err.message, 'error');
  }
}
btnPdf.addEventListener('click', exportPdf);
btnPdf2.addEventListener('click', exportPdf);


// ── Clear ─────────────────────────────────────────────────────
btnClear.addEventListener('click', () => {
  fileInput.value = '';
  dropZone.querySelector('div:nth-child(2)').textContent = 'Selecionar arquivo DICOM';
  dropZone.querySelector('.hint').innerHTML = 'Arraste e solte ou clique para escolher<br>Formato: .dcm (RT Plan)';
  btnParse.innerHTML = '⚡ Analisar DICOM';
  btnParse.disabled  = true;
  btnPdf.disabled    = true;
  btnClear.disabled  = true;
  parsedData = null;
  fotoBase64 = null;
  document.getElementById('fotoInput').value = '';
  document.getElementById('fotoPreview').style.display = 'none';
  document.getElementById('fotoIcon').style.display = '';
  document.getElementById('btnRemoveFoto').style.display = 'none';
  resetResult();
  hideStatus();
});


// ── Populate result ───────────────────────────────────────────
function populateResult(d) {
  setText('r-inst',  d.instituicao);
  setText('r-equip', d.equipamento);
  setText('r-nome',  d.nome_paciente);
  setText('r-id',    d.id_paciente);
  setText('r-sexo',  d.sexo);
  setText('r-dob',   d.dob);
  setText('r-idade', d.idade !== 'N/A' ? d.idade + ' anos' : 'N/A');
  setText('r-plano', d.nome_plano);
  setText('r-dose',  d.dose_total);
  setText('r-frac',  d.fracoes);
  setText('r-aprov',    d.data_aprovacao  || 'N/A');
  setText('r-aprovpor', d.aprovado_por    || 'N/A');


  // Desvio total no badge do cabeçalho da tabela de campos
  let somaCalc = 0, somaTPS = 0, countCalc = 0;
  d.campos.forEach(c => {
    const uc = parseFloat(c.um_calc);
    const ut = parseFloat(c.um);
    if (!isNaN(uc) && !isNaN(ut)) { somaCalc += uc; somaTPS += ut; countCalc++; }
  });
  const badge = document.getElementById('r-desvio-badge');
  if (countCalc > 0 && somaTPS !== 0) {
    const desvio = (somaCalc / somaTPS - 1) * 100;
    const abs_d  = Math.abs(desvio);
    const color  = abs_d <= 3 ? '#1e6641' : abs_d <= 5 ? '#7a5f00' : '#8b0000';
    const bg     = abs_d <= 3 ? '#e6f4ec' : abs_d <= 5 ? '#fff3cd' : '#fde8e8';
    badge.textContent = `Desvio Total: ${desvio.toFixed(1)}%`;
    badge.style.cssText = `display:inline-block;color:${color};background:${bg};padding:2px 10px;border-radius:3px;font-weight:700;font-size:11px;`;
  } else {
    badge.style.display = 'none';
  }
  setText('r-nfields', `(${d.campos.length} campo${d.campos.length !== 1 ? 's' : ''})`);


  const tbody = document.getElementById('r-campos');
  tbody.innerHTML = '';
  d.campos.forEach(c => {
    const tr = document.createElement('tr');


    let diffCell = 'N/A';
    if (c.diff_pct && c.diff_pct !== 'N/A') {
      const v = parseFloat(c.diff_pct);
      const abs_v = Math.abs(v);
      const color = abs_v <= 3 ? '#1e6641' : abs_v <= 5 ? '#7a5f00' : '#8b0000';
      const bg    = abs_v <= 3 ? '#e6f4ec' : abs_v <= 5 ? '#fff3cd' : '#fde8e8';
      diffCell = `<span style="color:${color};background:${bg};padding:2px 6px;border-radius:3px;font-weight:700;">${c.diff_pct}%</span>`;
    }


    const cells = [
      c.numero, c.nome, c.feixe,
      c.energia, c.filtro || '—', c.tecnica,
      c.campo_x1, c.campo_x2, c.campo_x_cm || 'N/A',
      c.campo_y1, c.campo_y2, c.campo_y_cm || 'N/A',
      c.dose,
      c.profundidade || 'N/A',
      c.tmr || 'N/A',
      c.tmrw || 'N/A',
      c.scp || 'N/A',
      c.um,
      c.um_calc || 'N/A',
    ].map(v => `<td>${v}</td>`).join('');


    tr.innerHTML = cells + `<td style="text-align:center;">${diffCell}</td>`;
    tbody.appendChild(tr);
  });
}


function setText(id, val) {
  document.getElementById(id).textContent = val || '—';
}


function resetResult() {
  resultDiv.style.display = 'none';
  ['r-inst','r-equip','r-nome','r-id','r-sexo','r-dob','r-idade',
   'r-plano','r-dose','r-frac','r-aprov','r-aprovpor'].forEach(id => setText(id, '—'));
  document.getElementById('r-desvio-badge').style.display = 'none';
  document.getElementById('r-campos').innerHTML = '';
}


function showStatus(msg, type) {
  statusBar.textContent = msg;
  statusBar.className   = type === 'error' ? 'error' : type === 'success' ? 'success' : '';
  statusBar.style.display = 'block';
}
function hideStatus() {
  statusBar.style.display = 'none';
}// ── Filtro Modal ──────────────────────────────────────────────
const filtroModal = document.getElementById('filtroModal');


function showFiltroModal(camposComFiltro) {
  const container = document.getElementById('filtroInputs');
  container.innerHTML = camposComFiltro.map(c => `
    <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
      <div style="flex:1;">
        <div style="font-weight:600;font-size:13px;">${c.nome} <span style="color:var(--muted);font-weight:400;">(Nº ${c.numero})</span></div>
        <div style="font-size:11px;color:var(--muted);">Filtro detectado: ${c.filtro} &nbsp;|&nbsp; Energia: ${c.energia} MeV</div>
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        <input type="number" step="1" min="0" max="90"
          id="angulo_${c.numero}"
          style="width:80px;padding:7px 10px;border:1px solid var(--border);border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:13px;"
          placeholder="graus">
        <span style="font-size:12px;color:var(--muted);">°</span>
      </div>
    </div>
  `).join('');
  filtroModal.classList.add('open');
}


document.getElementById('btnConfirmFiltro').addEventListener('click', async () => {
  // Coleta ângulos informados
  const angulos = {};
  parsedData.campos.forEach(c => {
    if (!c.filtro_presente) return;
    const input = document.getElementById(`angulo_${c.numero}`);
    if (input && input.value !== '') {
      angulos[c.numero] = parseFloat(input.value);
    }
  });


  // Valida que todos foram preenchidos
  const pendentes = parsedData.campos
    .filter(c => c.filtro_presente && angulos[c.numero] === undefined)
    .map(c => c.nome);
  if (pendentes.length > 0) {
    alert(`Informe o ângulo para: ${pendentes.join(', ')}`);
    return;
  }


  filtroModal.classList.remove('open');
  showStatus('Calculando UM com filtros...', 'loading');


  try {
    const res  = await fetch('/recalc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campos: parsedData.campos, angulos })
    });
    const json = await res.json();
    if (!res.ok || json.error) {
      showStatus('Erro no recálculo: ' + (json.error || ''), 'error');
      return;
    }
    // Atualiza parsedData e re-renderiza tabela
    parsedData.campos = json.campos;
    populateResult(parsedData);
    showStatus('UM calculada com os ângulos informados.', 'success');
  } catch(e) {
    showStatus('Erro: ' + e.message, 'error');
  }
});
const configModal = document.getElementById('configModal');
// ── Logo upload ───────────────────────────────────────────────
document.getElementById('btnUploadLogo').addEventListener('click', async () => {
  const file = document.getElementById('cfgLogoFile').files[0];
  if (!file) { logoStatus('Selecione um arquivo.', 'error'); return; }
  const fd = new FormData();
  fd.append('file', file);
  logoStatus('Enviando...', 'loading');
  try {
    const res  = await fetch('/logo/upload', { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok || json.error) { logoStatus('Erro: ' + json.error, 'error'); return; }
    logoStatus('✓ Logo salva com sucesso!', 'success');
    const prev = document.getElementById('logoPreview');
    prev.src = '/logo?' + Date.now();
    prev.style.display = '';
  } catch(e) { logoStatus('Erro: ' + e.message, 'error'); }
});


document.getElementById('btnDeleteLogo').addEventListener('click', async () => {
  if (!confirm('Remover a logo?')) return;
  const res  = await fetch('/logo/delete', { method: 'POST' });
  const json = await res.json();
  if (json.ok) {
    logoStatus('Logo removida.', 'success');
    document.getElementById('logoPreview').style.display = 'none';
  }
});


function logoStatus(msg, type) {
  const el = document.getElementById('cfgLogoStatus');
  el.textContent = msg;
  el.style.display = 'block';
  el.style.background = type === 'error' ? '#fde8e8' : type === 'success' ? '#e6f4ec' : '#fff3cd';
  el.style.border = '1px solid ' + (type === 'error' ? '#f5b7b7' : type === 'success' ? '#9ed8b4' : '#ffe89b');
  el.style.color  = type === 'error' ? '#8b0000' : type === 'success' ? '#1e6641' : '#7a5f00';
}


// ── Foto do paciente ──────────────────────────────────────────
let fotoBase64 = null;


document.getElementById('fotoInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    fotoBase64 = ev.target.result;
    const preview = document.getElementById('fotoPreview');
    preview.src = fotoBase64;
    preview.style.display = 'block';
    document.getElementById('fotoIcon').style.display = 'none';
    document.getElementById('btnRemoveFoto').style.display = 'block';
  };
  reader.readAsDataURL(file);
});


document.getElementById('btnRemoveFoto').addEventListener('click', () => {
  fotoBase64 = null;
  document.getElementById('fotoInput').value = '';
  document.getElementById('fotoPreview').style.display = 'none';
  document.getElementById('fotoIcon').style.display = '';
  document.getElementById('btnRemoveFoto').style.display = 'none';
});


document.getElementById('btnConfig').addEventListener('click', async () => {
  configModal.classList.add('open');
  try {
    const res = await fetch('/config');
    const cfg = await res.json();
    if (cfg.equipamento_fabricante) document.getElementById('cfgFabricante').value = cfg.equipamento_fabricante;
    renderFWList(cfg.fw || {});
    renderFDList(cfg.fd || {});
  } catch(e) {}
  loadTablesList();
});
document.getElementById('btnCloseModal').addEventListener('click',  () => configModal.classList.remove('open'));
document.getElementById('btnCloseModal2').addEventListener('click', () => configModal.classList.remove('open'));
configModal.addEventListener('click', e => { if (e.target === configModal) configModal.classList.remove('open'); });


// ── Salvar fabricante ─────────────────────────────────────────
document.getElementById('btnSaveFabricante').addEventListener('click', async () => {
  const fabricante = document.getElementById('cfgFabricante').value;
  if (!fabricante) { cfgConfigMsg('Selecione um fabricante.', 'error'); return; }
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ equipamento_fabricante: fabricante })
  });
  const json = await res.json();
  cfgConfigMsg(json.ok ? `✓ Fabricante salvo: ${fabricante}` : 'Erro ao salvar.', json.ok ? 'success' : 'error');
});


// ── Adicionar FW ──────────────────────────────────────────────
document.getElementById('btnAddFW').addEventListener('click', async () => {
  const energia = document.getElementById('cfgFWEnergia').value;
  const valor   = document.getElementById('cfgFWValor').value;
  if (!energia || !valor) { cfgConfigMsg('Informe energia e valor FW.', 'error'); return; }
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fw_energia: energia, fw_valor: valor })
  });
  const json = await res.json();
  if (json.ok) {
    cfgConfigMsg(`✓ FW ${valor} cadastrado para ${energia} MeV`, 'success');
    document.getElementById('cfgFWEnergia').value = '';
    document.getElementById('cfgFWValor').value   = '';
    renderFWList(json.config.fw || {});
  } else {
    cfgConfigMsg('Erro ao salvar FW.', 'error');
  }
});


async function deleteFW(energia) {
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fw_delete: energia })
  });
  const json = await res.json();
  if (json.ok) renderFWList(json.config.fw || {});
}


// ── FD ────────────────────────────────────────────────────────
document.getElementById('btnAddFD').addEventListener('click', async () => {
  const energia = document.getElementById('cfgFDEnergia').value;
  const valor   = document.getElementById('cfgFDValor').value;
  if (!energia || !valor) { cfgConfigMsg('Informe energia e valor FD.', 'error'); return; }
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fd_energia: energia, fd_valor: valor })
  });
  const json = await res.json();
  if (json.ok) {
    cfgConfigMsg(`✓ FD ${valor} cadastrado para ${energia} MeV`, 'success');
    document.getElementById('cfgFDEnergia').value = '';
    document.getElementById('cfgFDValor').value   = '';
    renderFDList(json.config.fd || {});
  } else {
    cfgConfigMsg('Erro ao salvar FD.', 'error');
  }
});


async function deleteFD(energia) {
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fd_delete: energia })
  });
  const json = await res.json();
  if (json.ok) renderFDList(json.config.fd || {});
}


function renderFDList(fd) {
  const el = document.getElementById('fdList');
  const entries = Object.entries(fd);
  if (!entries.length) {
    el.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:6px 0;">Nenhum FD cadastrado.</div>';
    return;
  }
  el.innerHTML = entries.map(([e, v]) => `
    <div class="table-row" style="padding:6px 10px;">
      <div class="t-meta" style="min-width:80px;">${e} MeV</div>
      <div class="t-name" style="font-family:'IBM Plex Mono',monospace;">FD = ${v}</div>
      <button class="t-del" onclick="deleteFD('${e}')" title="Remover">🗑</button>
    </div>`).join('');
}


function renderFWList(fw) {
  const el = document.getElementById('fwList');
  const entries = Object.entries(fw);
  if (!entries.length) {
    el.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:6px 0;">Nenhum FW cadastrado.</div>';
    return;
  }
  el.innerHTML = entries.map(([e, v]) => `
    <div class="table-row" style="padding:6px 10px;">
      <div class="t-meta" style="min-width:80px;">${e} MeV</div>
      <div class="t-name" style="font-family:'IBM Plex Mono',monospace;">FW = ${v}</div>
      <button class="t-del" onclick="deleteFW('${e}')" title="Remover">🗑</button>
    </div>`).join('');
}


function cfgConfigMsg(msg, type) {
  const el = document.getElementById('cfgConfigStatus');
  el.textContent = msg;
  el.style.display = 'block';
  el.style.background = type === 'error' ? '#fde8e8' : '#e6f4ec';
  el.style.border = '1px solid ' + (type === 'error' ? '#f5b7b7' : '#9ed8b4');
  el.style.color  = type === 'error' ? '#8b0000' : '#1e6641';
}


async function loadTablesList() {
  const res  = await fetch('/tables');
  const data = await res.json();
  const el   = document.getElementById('tablesList');
  const entries = Object.entries(data);
  if (!entries.length) {
    el.innerHTML = '<div class="empty-tables">Nenhuma tabela cadastrada.</div>';
    return;
  }
  el.innerHTML = entries.map(([tid, m]) => `
    <div class="table-row" id="trow-${tid}">
      <div>
        <span class="t-name">${m.name}</span>
        <span class="t-meta"> — ${m.category} | ${m.energia} MeV | ${m.n_rows} profundidades × ${m.n_cols} campos | enviado ${m.uploaded_at}</span>
      </div>
      <button class="t-del" onclick="deleteTable('${tid}')" title="Remover">🗑</button>
    </div>`).join('');
}


document.getElementById('btnUploadTable').addEventListener('click', async () => {
  const file     = document.getElementById('cfgFile').files[0];
  const categoria = document.getElementById('cfgCategory').value;
  const energia  = document.getElementById('cfgEnergia').value;
  const label    = document.getElementById('cfgLabel').value || (file ? file.name : '');
  const statusEl = document.getElementById('cfgStatus');


  if (!file)    { cfgMsg('Selecione um arquivo.', 'error'); return; }
  if (!energia) { cfgMsg('Informe a energia (MeV).', 'error'); return; }


  const fd = new FormData();
  fd.append('file',     file);
  fd.append('category', categoria);
  fd.append('energia',  energia);
  fd.append('label',    label);


  cfgMsg('Enviando...', 'loading');
  try {
    const res  = await fetch('/tables/upload', { method: 'POST', body: fd });
    const json = await res.json();
    if (!res.ok || json.error) { cfgMsg('Erro: ' + (json.error || ''), 'error'); return; }
    cfgMsg(`✓ Tabela "${json.meta.name}" cadastrada (${json.meta.n_rows} × ${json.meta.n_cols}).`, 'success');
    document.getElementById('cfgFile').value    = '';
    document.getElementById('cfgEnergia').value = '';
    document.getElementById('cfgLabel').value   = '';
    loadTablesList();
  } catch(e) {
    cfgMsg('Erro de conexão: ' + e.message, 'error');
  }
});


async function deleteTable(tid) {
  if (!confirm('Remover esta tabela?')) return;
  const res = await fetch(`/tables/${tid}`, { method: 'DELETE' });
  if (res.ok) loadTablesList();
}


function cfgMsg(msg, type) {
  const el = document.getElementById('cfgStatus');
  el.textContent = msg;
  el.style.display = 'block';
  el.style.background = type === 'error' ? '#fde8e8' : type === 'success' ? '#e6f4ec' : '#fff3cd';
  el.style.border = '1px solid ' + (type === 'error' ? '#f5b7b7' : type === 'success' ? '#9ed8b4' : '#ffe89b');
  el.style.color  = type === 'error' ? '#8b0000' : type === 'success' ? '#1e6641' : '#7a5f00';
}
</script>
</body>
</html>
"""




# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 54)
    print("  RT Plan DICOM Viewer")
    print("  Acesse: http://localhost:5000")
    print("=" * 54)
    app.run(debug=True, host="0.0.0.0", port=5000)
