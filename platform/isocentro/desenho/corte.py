"""O corte de TC desenhado: janela, estruturas e colorwash de dose, em PNG.

A ``CTSerie`` (``dicom/ct_series``) é o volume em HU e a geometria; daqui sai a
imagem que a tela e a ficha mostram. Até a R-58 isto era o método
``CTSerie.render`` — o desenho saiu do modelo para o modelo poder ir para
``rt/`` sem PIL. Quem desenha continua lendo a geometria da série (``zs``,
``ipp0``, ``psc_eff``/``psr_eff``) e a máscara do corpo dela, que é a MESMA
conversão pixel↔coordenada do resto do modelo: duplicá-la aqui é que faria os
dois lados se afastarem em silêncio.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw

from isocentro.dicom import ct_series

# Janelas (WL/WW em HU) usadas pelo visualizador. ``None`` = janela do próprio
# DICOM (a que o planejador exportou).
JANELAS: dict[str, tuple[float, float] | None] = {
    # (WL, WW) calculados a partir do range HU informado: WL=(lo+hi)/2, WW=hi-lo
    "W/L de aquisição": None,         # usa a janela exportada pelo TPS
    "Abdome":           ( 50,  350),  # -125 → 225  HU
    "Osso":             (200, 1200),  # -400 → 800  HU
    "Cerebelo":         ( 40,  120),  #  -20 → 100  HU
    "Fígado":           ( 50,  150),  #  -25 → 125  HU
    "Pulmão":           (-500, 1000), # -1000 → 0   HU
    "Pelve":            ( 40,  400),  # -160 → 240  HU
    "Mama":             (-50,  400),  # -250 → 150  HU
}

# Lado máximo (px) da imagem renderizada.
_LADO_MAX = 520

_ISODOSE_ALPHA = 0.50   # opacidade do colorwash



def _janela(serie, nome_ou_par) -> tuple[float, float]:
    if isinstance(nome_ou_par, tuple):
        return nome_ou_par
    par = JANELAS.get(nome_ou_par, None)
    return par if par is not None else (serie.wl_padrao, serie.ww_padrao)


def _para_cinza(serie, arr_hu: np.ndarray, janela) -> np.ndarray:
    wl, ww = _janela(serie, janela)
    lo, hi = wl - ww / 2.0, wl + ww / 2.0
    g = np.clip((arr_hu.astype(np.float32) - lo) / (hi - lo), 0, 1)
    return (g * 255).astype(np.uint8)


def renderizar_corte(serie, plano: str, idx: int, janela="W/L de aquisição",
                     rs=None, mostrar_estruturas: bool = True,
                     rd=None, mostrar_isodose: bool = True,
                     estruturas_visiveis: set | None = None,
                     isodose_range: tuple = (30.0, 100.0),
                     dose_grade=None, fundo: int = 255,
                     dose_ref: float | None = None) -> bytes:
    """Gera PNG de um corte: colorwash de dose + estruturas em todos os planos.

    ``dose_grade`` (tupla de ``tupla_dose``) sobrepõe ``rd`` — usado para a
    dose SOMA de vários planos na 'ficha soma'; ele já vem normalizado, então
    ``dose_ref`` só vale para o ``rd``.
    ``dose_ref`` (Gy): dose do 100% (a prescrição do plano). Sem ela, o 100%
    é o máximo da grade — referência que muda de plano para plano.
    ``fundo``: tom de cinza (0–255) fora do corpo (máscara EXTERNAL). 255 =
    branco (padrão, exigido no PDF); o app usa 0 (preto) para a visualização.
    """
    arr, (esc_y, esc_x) = serie._plano_cinza(plano, idx)
    cinza = _para_cinza(serie, arr, janela)
    rgb = np.dstack([cinza] * 3)

    z_axial: float | None = None
    if plano == "Axial":
        z_axial = float(serie.zs[int(np.clip(idx, 0, serie.n_axial - 1))])

    # Máscara do paciente (EXTERNAL + bólus): fundo fora do corpo E recorte
    # do colorwash, para a isodose não vazar para o ar (ver _mascara_corpo).
    corpo = serie._mascara_corpo(plano, idx, rs, z_axial) if rs is not None else None
    if corpo is not None:
        rgb[~corpo] = fundo

    img = Image.fromarray(rgb, "RGB")

    # Colorwash de isodose — todos os planos.
    if mostrar_isodose and (dose_grade is not None or rd is not None):
        grade = (dose_grade if dose_grade is not None
                 else ct_series._dose_pct_grade(rd, dose_ref))
        if grade is not None:
            dose_2d = None
            if plano == "Axial" and z_axial is not None:
                dose_2d = ct_series._amostrar_axial(
                    grade, serie.ipp0, serie.psr_eff, serie.psc_eff,
                    serie.rows, serie.cols, z_axial)
            elif plano == "Sagital":
                x_idx = int(np.clip(idx, 0, serie.cols - 1))
                dose_2d = ct_series._amostrar_sagital(
                    grade, serie.ipp0, serie.psr_eff, serie.psc_eff,
                    serie.zs, serie.rows, x_idx)
            elif plano == "Coronal":
                y_idx = int(np.clip(idx, 0, serie.rows - 1))
                dose_2d = ct_series._amostrar_coronal(
                    grade, serie.ipp0, serie.psr_eff, serie.psc_eff,
                    serie.zs, serie.cols, y_idx)
            if dose_2d is not None:
                img = _aplicar_colorwash(img, dose_2d, isodose_range,
                                         dentro=corpo)

    # Estruturas — todos os planos.
    if rs is not None and mostrar_estruturas:
        if plano == "Axial":
            _desenhar_estruturas_axial(serie, img, rs, idx, estruturas_visiveis)
        elif plano == "Sagital":
            img = _desenhar_estruturas_sagital(
                serie, img, rs, int(np.clip(idx, 0, serie.cols - 1)), estruturas_visiveis)
        elif plano == "Coronal":
            img = _desenhar_estruturas_coronal(
                serie, img, rs, int(np.clip(idx, 0, serie.rows - 1)), estruturas_visiveis)

    # Reescala para proporção física.
    h, w = cinza.shape
    alt_mm, larg_mm = h * esc_y, w * esc_x
    escala = _LADO_MAX / max(alt_mm, larg_mm)
    novo = (max(1, int(round(larg_mm * escala))), max(1, int(round(alt_mm * escala))))
    img = img.resize(novo, Image.BILINEAR)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _desenhar_estruturas_axial(serie, img: Image.Image, rs, idx: int,
                               estruturas_visiveis: set | None = None) -> None:
    draw = ImageDraw.Draw(img)
    for r in ct_series._contornos_por_roi(rs).values():
        if r["tipo"] == "EXTERNAL":
            continue
        if estruturas_visiveis is not None and r["nome"] not in estruturas_visiveis:
            continue
        for pts in r["contornos"]:
            # Exibe o contorno apenas no corte mais próximo — evita duplicatas
            zi_mais_prox = int(np.argmin(np.abs(serie.zs - float(pts[0, 2]))))
            if zi_mais_prox != idx:
                continue
            col = (pts[:, 0] - serie.ipp0[0]) / serie.psc_eff
            row = (pts[:, 1] - serie.ipp0[1]) / serie.psr_eff
            poly = list(zip(col, row))
            draw.polygon(poly, outline=r["cor"])


def _desenhar_estruturas_sagital(serie, img: Image.Image, rs, x_idx: int,
                                 estruturas_visiveis: set | None = None) -> Image.Image:
    """Desenha a BORDA da seção sagital (x = x_idx) de cada estrutura.

    Usa a máscara preenchida corte a corte (ver ``_mask_sagital``) e pinta só
    o seu contorno. Antes traçava-se uma silhueta esquerda/direita a partir
    do min/max de x por corte: isso unia partes distintas num mesmo Z
    (costelas, pulmões) com uma linha horizontal que não existe. A máscara
    preenche cada par de cruzamentos separadamente, então cada parte fica com
    seu próprio contorno.
    """
    arr = np.array(img)
    for r in ct_series._contornos_por_roi(rs).values():
        if r["tipo"] == "EXTERNAL":
            continue
        if estruturas_visiveis is not None and r["nome"] not in estruturas_visiveis:
            continue
        mask = serie._mask_sagital(r["contornos"], x_idx)
        if mask.any():
            arr[_borda(mask)] = r["cor"]
    return Image.fromarray(arr, "RGB")


def _desenhar_estruturas_coronal(serie, img: Image.Image, rs, y_idx: int,
                                 estruturas_visiveis: set | None = None) -> Image.Image:
    """Desenha a BORDA da seção coronal (y = y_idx) de cada estrutura.

    Mesmo princípio de ``_desenhar_estruturas_sagital``: contorno da máscara
    preenchida, sem a linha horizontal espúria que o min/max criava ao unir
    partes separadas de uma mesma estrutura num dado Z.
    """
    arr = np.array(img)
    for r in ct_series._contornos_por_roi(rs).values():
        if r["tipo"] == "EXTERNAL":
            continue
        if estruturas_visiveis is not None and r["nome"] not in estruturas_visiveis:
            continue
        mask = serie._mask_coronal(r["contornos"], y_idx)
        if mask.any():
            arr[_borda(mask)] = r["cor"]
    return Image.fromarray(arr, "RGB")



def _colormap_frio_quente(t: "np.ndarray") -> "np.ndarray":
    """Gradiente contínuo azul→ciano→verde→amarelo→vermelho para t ∈ [0, 1].

    Retorna array (…, 3) float32 em [0, 255].
    Pontos de controle:
        t=0.00 → azul    (  0,   0, 255)
        t=0.25 → ciano   (  0, 255, 255)
        t=0.50 → verde   (  0, 255,   0)
        t=0.75 → amarelo (255, 255,   0)
        t=1.00 → vermelho(255,   0,   0)
    """
    t = np.clip(t, 0.0, 1.0)
    r = np.where(t < 0.50, 0.0,
        np.where(t < 0.75, 4.0 * (t - 0.50), 1.0))
    g = np.where(t < 0.25, 4.0 * t,
        np.where(t < 0.75, 1.0,
        1.0 - 4.0 * (t - 0.75)))
    b = np.where(t < 0.25, 1.0,
        np.where(t < 0.50, 1.0 - 4.0 * (t - 0.25), 0.0))
    return np.stack([r, g, b], axis=-1).astype(np.float32) * 255.0



def _aplicar_colorwash(img: Image.Image, dose_pct: np.ndarray,
                       isodose_range: tuple,
                       dentro: "np.ndarray | None" = None) -> Image.Image:
    """Colorwash contínuo azul→vermelho mapeado ao range escolhido pelo usuário.

    lo% → azul (frio), hi% → vermelho (quente). Abaixo de lo não há overlay;
    ACIMA de hi satura no vermelho, não some. Com o 100% no máximo da grade
    nada passava de 100% e o corte superior nunca era exercido; com o 100% na
    PRESCRIÇÃO o ponto quente passa dela (~115%) e descartá-lo abriria um buraco
    transparente bem no meio do alvo. A cor não depende de limiares fixos —
    escala com [lo, hi].
    """
    lo, hi = float(isodose_range[0]), float(isodose_range[1])
    if hi <= lo:
        return img

    img_arr = np.array(img, dtype=np.float32)

    # Normaliza dose no range do usuário: lo→0 (azul), hi→1 (vermelho); acima
    # de hi fica preso em 1 (vermelho), não vira transparente.
    t = np.clip((dose_pct - lo) / (hi - lo), 0.0, 1.0)

    # Abaixo de lo não há overlay; fora do paciente também não. A grade de dose
    # do TPS não para na pele — sem o recorte, a isodose saía flutuando no ar ao
    # lado do corpo. Onde há bólus a máscara já o inclui, porque ali a dose fora
    # do contorno externo é real (ver _mascara_corpo).
    mostrar = dose_pct >= lo
    if dentro is not None and dentro.shape == dose_pct.shape:
        mostrar &= dentro

    overlay = _colormap_frio_quente(t)          # (rows, cols, 3)
    alpha = np.where(mostrar, _ISODOSE_ALPHA, 0.0)[..., np.newaxis]

    img_arr = img_arr * (1.0 - alpha) + overlay * alpha
    return Image.fromarray(np.clip(img_arr, 0, 255).astype(np.uint8), "RGB")



def _borda(mask: np.ndarray) -> np.ndarray:
    """Pixels de contorno de uma máscara: True onde é borda da região preenchida.

    Um pixel é interior quando ele e os quatro vizinhos ortogonais estão todos
    dentro da máscara; o restante da máscara é borda. Serve para desenhar o
    contorno da seção reconstruída (coronal/sagital) sem preenchê-la.
    """
    interior = np.zeros_like(mask)
    interior[1:-1, 1:-1] = (
        mask[1:-1, 1:-1] & mask[:-2, 1:-1] & mask[2:, 1:-1]
        & mask[1:-1, :-2] & mask[1:-1, 2:]
    )
    return mask & ~interior
