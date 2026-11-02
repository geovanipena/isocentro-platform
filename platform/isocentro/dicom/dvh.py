"""Cálculo do DVH (histograma dose-volume) a partir de RT Dose + RT Struct.

Para cada estrutura, os contornos (axiais, ``CLOSED_PLANAR``) são rasterizados
sobre a grade de dose do RT Dose, amostrando a dose dos voxels internos e
montando o DVH cumulativo (volume % × dose).
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

def _z_das_frames(rd) -> np.ndarray:
    z0 = float(rd.ImagePositionPatient[2])
    return np.array([z0 + float(o) for o in rd.GridFrameOffsetVector])


def _mapa_roi(rs) -> dict[int, str]:
    return {int(r.ROINumber): str(r.ROIName) for r in rs.StructureSetROISequence}


def _mascara_estrutura(contornos, rd, zgrid, dose_shape) -> dict[int, np.ndarray]:
    """Rasteriza os contornos da estrutura em máscaras 2D por frame de dose."""
    frames, rows, cols = dose_shape
    ipp = [float(v) for v in rd.ImagePositionPatient]
    psr, psc = float(rd.PixelSpacing[0]), float(rd.PixelSpacing[1])
    dz = abs(zgrid[1] - zgrid[0]) if len(zgrid) > 1 else 1.0
    mascaras: dict[int, np.ndarray] = {}
    for c in contornos:
        pts = np.array(c.ContourData, dtype=float).reshape(-1, 3)
        k = int(np.argmin(np.abs(zgrid - pts[0, 2])))
        if abs(zgrid[k] - pts[0, 2]) > dz:
            continue
        col = (pts[:, 0] - ipp[0]) / psc
        row = (pts[:, 1] - ipp[1]) / psr
        img = Image.new("1", (cols, rows), 0)
        ImageDraw.Draw(img).polygon(list(zip(col, row)), fill=1)
        m = np.array(img, dtype=bool)
        # Múltiplos contornos no mesmo plano (ilhas/buracos) -> XOR.
        mascaras[k] = np.logical_xor(mascaras[k], m) if k in mascaras else m
    return mascaras


def calcular_dvh(rd, rs, nomes: list[str], n_bins: int = 200) -> dict:
    """Calcula o DVH cumulativo das estruturas a partir de UM RT Dose."""
    from isocentro.dicom import dose3d
    return calcular_dvh_grade(dose3d.grade_de_rd(rd), rs, nomes, n_bins)


def _mascara_grade(contornos, grade) -> dict[int, np.ndarray]:
    """Rasteriza contornos em máscaras 2D por frame de uma ``GradeDose``."""
    nz, ny, nx = grade.dose.shape
    x0, y0 = float(grade.x[0]), float(grade.y[0])
    dx = float(grade.x[1] - grade.x[0]) if nx > 1 else 1.0
    dy = float(grade.y[1] - grade.y[0]) if ny > 1 else 1.0
    zg = grade.z
    dz = abs(zg[1] - zg[0]) if nz > 1 else 1.0
    mascaras: dict[int, np.ndarray] = {}
    for c in contornos:
        pts = np.array(c.ContourData, dtype=float).reshape(-1, 3)
        k = int(np.argmin(np.abs(zg - pts[0, 2])))
        if abs(zg[k] - pts[0, 2]) > dz:
            continue
        col = (pts[:, 0] - x0) / dx
        row = (pts[:, 1] - y0) / dy
        img = Image.new("1", (nx, ny), 0)
        ImageDraw.Draw(img).polygon(list(zip(col, row)), fill=1)
        m = np.array(img, dtype=bool)
        mascaras[k] = np.logical_xor(mascaras[k], m) if k in mascaras else m
    return mascaras


def _contornos_da_estrutura(rs, nome: str):
    """A ``ContourSequence`` da estrutura pelo NOME, ou ``None``.

    O RT Struct guarda o nome num lugar (``StructureSetROISequence``) e os
    contornos em outro (``ROIContourSequence``), ligados pelo número da ROI —
    e a ordem das duas sequências não é a mesma. Casar por posição funcionava
    na maioria dos casos e trocava as estruturas nos outros.
    """
    num = None
    for r in rs.StructureSetROISequence:
        if str(r.ROIName) == nome:
            num = int(r.ROINumber)
            break
    if num is None:
        return None
    rc = next((r for r in rs.ROIContourSequence
               if int(r.ReferencedROINumber) == num), None)
    if rc is None:
        return None
    return getattr(rc, "ContourSequence", None) or None


def _espessura_dos_contornos(zs) -> float:
    """Distância típica entre dois cortes CONTORNADOS, em mm.

    A mediana, e não a média: uma estrutura com um salto no meio (o alvo que
    pula os cortes onde não aparece) teria a média puxada pelo salto, e a fatia
    de todo mundo engordaria por causa de um buraco.
    """
    unicos = np.unique(np.round(np.asarray(zs, dtype=float), 3))
    if unicos.size < 2:
        return 0.0
    return float(np.median(np.diff(unicos)))


def mascara_3d(grade, rs, nome: str):
    """Máscara booleana ``(nz, ny, nx)`` da estrutura sobre a grade de dose.

    O DVH não precisa dela — para amostrar a dose basta o par frame↔máscara 2D
    que ``_mascara_grade`` devolve. Os índices de CONFORMIDADE precisam: ``CI``
    e Paddick comparam o VOLUME da estrutura com o volume de uma isodose, e isso
    é contar voxels dos dois lados na mesma grade.

    **Por que não é só empilhar o que ``_mascara_grade`` devolve.** Aquela
    função põe cada contorno no frame de dose MAIS PRÓXIMO e pronto. Quando o
    corte da TC é mais grosso que o passo da grade de dose — no TC8, 5 mm de TC
    contra 2,5 mm de dose — metade dos frames dentro do alvo fica VAZIA: medido,
    o PTV_Mama ocupava 42 frames de dose num intervalo de 83. Para o DVH isso
    não faz diferença, porque a curva é relativa e amostrar um corte sim, um
    não, dá a mesma distribuição. Para o volume faz toda: os 758 cc do PTV_Mama
    eram METADE do volume real, e o índice de Paddick — que cruza o volume do
    alvo com o da isodose, esta contada em TODOS os frames — saía 0,20 num plano
    cujo CI RTOG era 1,25. Um Paddick de 0,20 é um plano inaceitável; o plano
    estava bom.

    Por isso cada contorno é espalhado pela ESPESSURA que ele representa. A
    conta é deliberadamente feita aqui e não dentro de ``_mascara_grade``: o
    DVH da ficha impressa passa por lá, e mexer no que já está no papel não
    entra de carona numa aba nova.

    Devolve ``None`` quando a estrutura não existe ou está vazia — ROI criada e
    nunca contornada é comum no acervo, e um cubo todo falso faria o volume sair
    0,0 cc em vez de "não há".
    """
    contornos = _contornos_da_estrutura(rs, nome)
    if contornos is None:
        return None

    nz, ny, nx = grade.dose.shape
    x0, y0 = float(grade.x[0]), float(grade.y[0])
    dx = float(grade.x[1] - grade.x[0]) if nx > 1 else 1.0
    dy = float(grade.y[1] - grade.y[0]) if ny > 1 else 1.0
    zg = np.asarray(grade.z, dtype=float)
    dz = abs(zg[1] - zg[0]) if nz > 1 else 1.0

    # Agrupar por PLANO antes de rasterizar. Os contornos de um mesmo z são
    # ilhas e buracos da mesma estrutura e se combinam por XOR (é o buraco que
    # precisa disso); os de z DIFERENTES não — dois contornos vizinhos que
    # caíssem no mesmo frame se cancelariam onde se sobrepõem, e a estrutura
    # ficaria com um rombo no meio.
    por_z: dict[float, list] = {}
    for c in contornos:
        pts = np.array(c.ContourData, dtype=float).reshape(-1, 3)
        por_z.setdefault(round(float(pts[0, 2]), 3), []).append(pts)
    if not por_z:
        return None

    espessura = _espessura_dos_contornos(list(por_z)) or dz
    meia = espessura / 2.0

    cubo = np.zeros((nz, ny, nx), dtype=bool)
    for z, grupo in por_z.items():
        plano = np.zeros((ny, nx), dtype=bool)
        for pts in grupo:
            col = (pts[:, 0] - x0) / dx
            row = (pts[:, 1] - y0) / dy
            img = Image.new("1", (nx, ny), 0)
            ImageDraw.Draw(img).polygon(list(zip(col, row)), fill=1)
            plano = np.logical_xor(plano, np.array(img, dtype=bool))
        if not plano.any():
            continue
        # Os frames que esta fatia cobre. O ``argmin`` garante pelo menos um
        # mesmo quando a grade de dose é mais grossa que o corte da TC (a
        # situação inversa, em que várias fatias disputam o mesmo frame): sem
        # ele, uma estrutura fina não entraria em frame nenhum.
        alcanca = np.flatnonzero(np.abs(zg - z) <= meia + 1e-6)
        if alcanca.size == 0:
            k = int(np.argmin(np.abs(zg - z)))
            if abs(zg[k] - z) > max(dz, espessura):
                continue      # fatia fora da grade de dose
            alcanca = np.array([k])
        cubo[alcanca] |= plano
    return cubo if cubo.any() else None


def calcular_dvh_grade(grade, rs, nomes: list[str], n_bins: int = 200) -> dict:
    """DVH cumulativo das estruturas amostrando uma ``GradeDose`` (Gy).

    Aceita a dose SOMA de vários planos (``dose3d.somar``) ou a de um único
    plano (``dose3d.grade_de_rd``). Devolve
    ``{nome: {'dose', 'volume', 'd_max', 'd_media', 'd_min'}}``.
    """
    dose = grade.dose  # (nz, ny, nx) em Gy
    roi_nome = _mapa_roi(rs)
    nome_roi = {v: k for k, v in roi_nome.items()}

    resultado: dict[str, np.ndarray] = {}
    for nome in nomes:
        num = nome_roi.get(nome)
        if num is None:
            continue
        rc = next((r for r in rs.ROIContourSequence if int(r.ReferencedROINumber) == num), None)
        if rc is None or not getattr(rc, "ContourSequence", None):
            continue
        mascaras = _mascara_grade(rc.ContourSequence, grade)
        amostras = [dose[k][m] for k, m in mascaras.items() if m.any()]
        if not amostras:
            continue
        resultado[nome] = np.concatenate(amostras).astype(np.float64)
    return _curvas(resultado, n_bins)


def _curvas(amostras_por_nome: dict[str, np.ndarray], n_bins: int) -> dict:
    d_max_geral = max((v.max() for v in amostras_por_nome.values()), default=1.0)
    bins = np.linspace(0, d_max_geral * 1.02, n_bins)
    curvas = {}
    for nome, valores in amostras_por_nome.items():
        total = valores.size
        volume = np.array([100.0 * np.count_nonzero(valores >= b) / total for b in bins])
        curvas[nome] = {
            "dose": bins,
            "volume": volume,
            "d_max": float(valores.max()),
            "d_media": float(valores.mean()),
            "d_min": float(valores.min()),
        }
    return curvas
