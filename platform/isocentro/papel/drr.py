"""Renderização dos DRRs de conferência (páginas de setup do 600CD).

O DICOM RT Image traz o DRR em tons de cinza (osso claro sobre fundo escuro). A
ficha institucional o mostra invertido, com leve tom azulado (colormap ``bone_r``)
e um retículo vermelho graduado centrado no isocentro (marcas de 1 cm, longas a
cada 5 cm). Aqui reproduzimos exatamente isso a partir dos pixels do RT Image.
"""
from __future__ import annotations

import io

from isocentro.dicom import dicom_rt

# Vermelho do retículo, igual ao modelo impresso.
_VERMELHO = (237, 28, 36)


def render_drr(ds, cor=_VERMELHO) -> bytes:
    """PNG (bytes) do DRR já invertido/colorido e com o retículo no isocentro."""
    import numpy as np
    from PIL import Image, ImageDraw
    from matplotlib import colormaps

    g = dicom_rt.drr_geometria(ds)
    px = np.asarray(g["pixels"], dtype=float)
    lo, hi = float(px.min()), float(px.max())
    norm = np.clip((px - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    rgb = (colormaps["bone_r"](norm)[:, :, :3] * 255).astype("uint8")
    img = Image.fromarray(rgb, mode="RGB")

    rows, cols = px.shape[:2]
    draw = ImageDraw.Draw(img)
    cx, cy = g["col_iso"], g["lin_iso"]
    lw = max(2, round(cols / 300))          # espessura das linhas do retículo
    curto = max(3.0, cols * 0.011)          # meia-marca de 1 cm
    longo = curto * 2.0                     # meia-marca de 5 cm

    # Eixos.
    draw.line([(cx, 0), (cx, rows)], fill=cor, width=lw)
    draw.line([(0, cy), (cols, cy)], fill=cor, width=lw)

    # Marcas de 1 cm (longas a cada 5 cm) ao longo de cada eixo.
    passo_v = 10.0 / (g["esp_lin"] or 1.0)   # px por cm no eixo vertical
    passo_h = 10.0 / (g["esp_col"] or 1.0)   # px por cm no eixo horizontal
    for k in range(1, int(max(rows, cols) / min(passo_v, passo_h)) + 2):
        meia = longo if k % 5 == 0 else curto
        dv = k * passo_v
        for y in (cy - dv, cy + dv):
            if 0 <= y <= rows:
                draw.line([(cx - meia, y), (cx + meia, y)], fill=cor, width=lw)
        dh = k * passo_h
        for x in (cx - dh, cx + dh):
            if 0 <= x <= cols:
                draw.line([(x, cy - meia), (x, cy + meia)], fill=cor, width=lw)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
