"""Classificação automática do quadrante da lesão a partir do relatório
INTRABEAM (ZEISS).

Lê a página 2 do relatório de tratamento, detecta no diagrama "Application Type":
  • o cruzamento das linhas vermelhas  → posição da lesão
  • as esferas concêntricas (preto)    → mamilo (esfera menor) / aréola (maior)
  • a grade amarela                    → calibração do plano cartesiano (0–10)

e aplica a regra definida pela equipe:
  • cruz dentro da esfera maior (aréola)        → Areolar / periareolar
  • cruz sobre o eixo X ou Y do mamilo (± tol)  → Junção dos quadrantes
  • caso contrário                              → QSL / QSM / QIL / QIM
    (superior/inferior pelo Y; lateral/medial pelo X conforme a mama)

Dependências pesadas (cv2, pdf2image) são importadas de forma preguiçosa para
não onerar a inicialização do app quando a página não é usada.
"""
import io
import re
from math import hypot

import numpy as np


def _cluster(idx, gap=3):
    """Agrupa índices de pixel consecutivos e devolve o centro de cada grupo."""
    if len(idx) == 0:
        return []
    out, grp = [], [idx[0]]
    for v in idx[1:]:
        if v - grp[-1] <= gap:
            grp.append(v)
        else:
            out.append(int(np.mean(grp)))
            grp = [v]
    out.append(int(np.mean(grp)))
    return out


def parse_laterality(text):
    """'Right'/'Left' a partir de 'Application Type: ... Breast' no texto."""
    m = re.search(r"Application Type:\s*(Right|Left)\s*Breast", text, re.I)
    return m.group(1).capitalize() if m else None


def read_laterality(pdf_bytes):
    """Lê 'Application Type: Right/Left Breast' do texto do PDF."""
    return parse_laterality(read_text(pdf_bytes))


def read_patient_id(pdf_bytes):
    """Lê o campo 'Patient ID' do relatório (chave para casar com a linha do CSV)."""
    from pypdf import PdfReader

    txt = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    m = re.search(r"Patient ID\s+(\S+)", txt)
    return m.group(1).strip() if m else None


# Rótulos da página 1 do relatório INTRABEAM (label seguido do valor na mesma linha).
_REPORT_FIELDS = (
    "Patient Given Name", "Patient Family Name", "Patient ID", "Treatment #",
    "Insurance ID", "Other ID", "Treatment Date", "Prescribing Physician",
    "Responsible Physicist", "Applicator Size [cm]", "Applicator Serial Number",
    "Applicator Sterilizations to Date", "Dose Delivered [Gy]",
    "Deviation from Prescription [%]",
)


def read_text(pdf_bytes):
    """Texto concatenado de todas as páginas do PDF (vazio se for imagem/scan)."""
    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)


def parse_fields(text):
    """Extrai os campos do relatório INTRABEAM a partir do texto da página 1
    → dict {label: valor}. Rótulos testados do mais longo p/ o mais curto."""
    labels = sorted(_REPORT_FIELDS, key=len, reverse=True)
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        for lab in labels:
            if lab not in out and line.startswith(lab):
                out[lab] = line[len(lab):].strip()
                break
    return out


def read_fields(pdf_bytes):
    """Extrai os campos da página 1 do relatório INTRABEAM → dict {label: valor}."""
    return parse_fields(read_text(pdf_bytes))


def render_page(pdf_bytes, page=2, dpi=150):
    """Renderiza a página indicada do PDF como array RGB (uint8).
    O timeout evita que um PDF malformado trave o poppler indefinidamente."""
    from pdf2image import convert_from_bytes

    imgs = convert_from_bytes(pdf_bytes, dpi=dpi, first_page=page, last_page=page,
                              timeout=60)
    if not imgs:
        raise ValueError(f"PDF não tem a página {page}.")
    return np.asarray(imgs[0].convert("RGB"))


def _calibrate(rgb):
    """Calibra o plano cartesiano (0–10) a partir da grade amarela.

    Retorna (ux, uy, box_px) onde ux/uy convertem pixel → unidade do gráfico e
    box_px = (x0, x10, y10, y0) são os limites do gráfico em pixels.
    """
    R, G, B = (rgb[:, :, i].astype(int) for i in range(3))
    yellow = (R > 140) & (G > 120) & (B < 110)
    colct, rowct = yellow.sum(axis=0), yellow.sum(axis=1)
    vx = _cluster(np.where(colct > colct.max() * 0.5)[0])
    hy = _cluster(np.where(rowct > rowct.max() * 0.5)[0])
    if len(vx) < 3 or len(hy) < 3:
        raise ValueError("Não foi possível detectar a grade do diagrama.")
    sx, sy = float(np.median(np.diff(vx))), float(np.median(np.diff(hy)))
    # As linhas 0 e 10 coincidem com a moldura preta; a 1ª grade amarela é o 1.
    x0 = vx[0] - sx        # pixel de x = 0
    y0px = hy[-1] + sy     # pixel de y = 0
    ux = lambda px: (px - x0) / sx
    uy = lambda py: (y0px - py) / sy
    box = (int(x0), int(vx[-1] + sx), int(hy[0] - sy), int(y0px))
    return ux, uy, sx, sy, box


def detect(rgb):
    """Detecta cruz vermelha e esferas. Devolve dict com coordenadas em unidades
    do gráfico e nas coordenadas de pixel (para sobreposição)."""
    import cv2

    R, G, B = (rgb[:, :, i].astype(int) for i in range(3))
    ux, uy, sx, sy, box = _calibrate(rgb)
    x0i, x10i, y10i, y0i = box

    # ── cruz vermelha (lesão) ──
    red = (R > 150) & (G < 90) & (B < 90)
    if red.sum() < 50:
        raise ValueError("Linhas vermelhas (lesão) não encontradas.")
    cross_px = (int(np.argmax(red.sum(axis=0))), int(np.argmax(red.sum(axis=1))))
    cross = (round(ux(cross_px[0]), 2), round(uy(cross_px[1]), 2))

    # ── esferas concêntricas (mamilo/aréola) ──
    black = (((R < 90) & (G < 90) & (B < 90)).astype(np.uint8)) * 255
    mask = np.zeros_like(black)
    mask[y10i:y0i, x0i:x10i] = black[y10i:y0i, x0i:x10i]
    circ = cv2.HoughCircles(
        mask, cv2.HOUGH_GRADIENT, dp=1, minDist=18,
        param1=120, param2=18, minRadius=8, maxRadius=70,
    )
    if circ is None:
        raise ValueError("Esferas (mamilo/aréola) não encontradas.")
    cand = []
    for cxp, cyp, rp in circ[0]:
        ucx, ucy = ux(cxp), uy(cyp)
        if 1.5 <= ucx <= 8.5 and 1.5 <= ucy <= 8.5:  # descarta contorno da mama
            cand.append((ucx, ucy, rp / sx, cxp, cyp, rp))
    if not cand:
        raise ValueError("Esferas não localizadas na região central.")
    cand = np.array(cand, float)
    med = np.median(cand[:, :2], axis=0)                       # centro provável
    near = cand[np.hypot(cand[:, 0] - med[0], cand[:, 1] - med[1]) <= 0.7]
    nipple = (round(float(np.median(near[:, 0])), 2), round(float(np.median(near[:, 1])), 2))
    areola_r = round(float(near[:, 2].max()), 2)               # esfera maior
    nip_px = (int(np.median(near[:, 3])), int(np.median(near[:, 4])))
    areola_r_px = int(near[:, 5].max())

    return {
        "cross": cross, "nipple": nipple, "areola_r": areola_r,
        "cross_px": cross_px, "nipple_px": nip_px, "areola_r_px": areola_r_px,
        "box": box,
    }


def classify(nipple, areola_r, cross, laterality, junction_tol=0.5):
    """Aplica a regra geométrica. Devolve (codigo, descricao)."""
    cx, cy = nipple
    lx, ly = cross
    dx, dy = lx - cx, ly - cy
    if hypot(dx, dy) <= areola_r:
        return "Areolar", "Areolar / periareolar"
    if abs(dx) <= junction_tol or abs(dy) <= junction_tol:
        return "Junção", "Junção dos quadrantes"
    vert = "S" if dy > 0 else "I"
    lat = (laterality or "").lower()
    if lat.startswith("r"):       # mama direita: lateral = X baixo
        horiz = "L" if dx < 0 else "M"
    else:                          # mama esquerda: lateral = X alto
        horiz = "L" if dx > 0 else "M"
    code = f"Q{vert}{horiz}"
    nomes = {
        "QSL": "Quadrante súpero-lateral", "QSM": "Quadrante súpero-medial",
        "QIL": "Quadrante ínfero-lateral", "QIM": "Quadrante ínfero-medial",
    }
    return code, nomes[code]


def annotate(rgb, det):
    """Desenha a detecção sobre a imagem (cópia) para conferência visual."""
    import cv2

    out = rgb.copy()
    cx, cy = det["nipple_px"]
    cv2.circle(out, (cx, cy), det["areola_r_px"], (0, 160, 0), 2)   # aréola
    cv2.drawMarker(out, (cx, cy), (0, 120, 0), cv2.MARKER_CROSS, 18, 2)
    lx, ly = det["cross_px"]
    cv2.drawMarker(out, (lx, ly), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 26, 3)
    return out


def classify_pdf(pdf_bytes, laterality=None, junction_tol=0.5, page=2, dpi=150):
    """Pipeline completo: PDF → quadrante. Devolve dict com resultado e detecção."""
    lat = laterality or read_laterality(pdf_bytes)
    if not lat:
        raise ValueError("Lateralidade (Right/Left Breast) não encontrada no PDF.")
    rgb = render_page(pdf_bytes, page=page, dpi=dpi)
    det = detect(rgb)
    code, desc = classify(det["nipple"], det["areola_r"], det["cross"], lat, junction_tol)
    return {
        "laterality": lat, "code": code, "description": desc,
        "rgb": rgb, **det,
    }
