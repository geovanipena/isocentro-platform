"""Soma de doses 3D (RTDOSE) numa grade comum — base da 'ficha soma' multi-plano.

Cada RT Dose de um plano tem sua própria grade (posição/extensão/resolução),
mesmo quando os planos compartilham a tomografia. Para somar, cada dose é
reamostrada (interpolação trilinear separável, só numpy) numa grade comum que
cobre a união das grades, e então somada em **Gy absoluto**.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from isocentro.dicom import dicom_rt


@dataclass
class GradeDose:
    """Dose 3D em Gy absoluto sobre eixos regulares crescentes (mm)."""
    dose: np.ndarray   # (nz, ny, nx)
    z: np.ndarray      # (nz,)
    y: np.ndarray      # (ny,)
    x: np.ndarray      # (nx,)


def frame_uid(ds) -> str:
    """FrameOfReferenceUID de um RT Dose/Struct (identifica a tomografia).

    O RT Dose traz o UID no topo. O RT Struct NÃO — ele guarda o frame em
    ``ReferencedFrameOfReferenceSequence``. Sem este fallback, um plano que só
    tem RS (sem RD) ficava com frame vazio e, havendo mais de uma TC, não casava
    com nenhuma série: os cortes do paciente sumiam (viewer em branco).
    """
    fu = str(getattr(ds, "FrameOfReferenceUID", "") or "")
    if fu:
        return fu
    seq = getattr(ds, "ReferencedFrameOfReferenceSequence", None)
    if seq:
        try:
            return str(seq[0].FrameOfReferenceUID or "")
        except (AttributeError, IndexError, TypeError):
            pass
    return ""


def grade_de_rd(rd) -> GradeDose:
    """Extrai a grade de dose (Gy) de um RT Dose, com eixos crescentes.

    Solta o ``pixel_array`` que o pydicom cacheia no dataset: a grade em Gy já
    tem o dado, e num plano com vários RT Dose (a ficha soma) cada cache
    segurava uma cópia uint32 do tamanho da grade — centenas de MB por plano.
    """
    escala = float(getattr(rd, "DoseGridScaling", 1.0))
    dose = rd.pixel_array.astype(np.float32)                   # (nz, ny, nx)
    dose *= escala                                             # in-place: 1 cópia, não 2
    dicom_rt.soltar_cache_pixels(rd)
    z, y, x = _eixos_brutos_de_rd(rd)
    return _crescente(GradeDose(dose, z, y, x))


def _eixos_brutos_de_rd(rd) -> tuple:
    """(z, y, x) da grade de um RT Dose direto do cabeçalho, no sentido do arquivo.

    ``Rows``/``Columns``/``GridFrameOffsetVector`` são as MESMAS tags que o
    pydicom usa para remontar o ``pixel_array``: ``dose.shape`` é sempre
    ``(len(offsets), Rows, Columns)``. Por isso derivar a geometria daqui e
    derivá-la do array decodificado são a mesma coisa — não duas fontes que
    possam divergir. É o que deixa ``grade_de_rd`` e ``_eixos_de_rd``
    concordarem por construção.

    ``PixelSpacing`` é sempre positivo; quem dá o SENTIDO dos eixos é o
    ``ImageOrientationPatient`` — [−1,0,0, 0,−1,0] em decúbito ventral (HFP/FFP),
    onde x e y DIMINUEM a partir do IPP. Ignorar isso espelhava a grade em torno
    do IPP: a dose do prono caía fora do paciente. ``_crescente`` reordena depois.
    """
    ipp = [float(v) for v in rd.ImagePositionPatient]
    sr, sc = dicom_rt.sinais_iop(rd)
    psr = float(rd.PixelSpacing[0]) * sr                       # linhas → y
    psc = float(rd.PixelSpacing[1]) * sc                       # colunas → x
    offsets = np.array([float(o) for o in rd.GridFrameOffsetVector], dtype=np.float64)
    # Os offsets andam ao longo da NORMAL do plano (linha × coluna), não do Z do
    # paciente — e no FFS a normal aponta para −Z. Somando sempre, a grade caía
    # uma grade inteira fora do paciente (ver ``dicom_rt.sinal_normal_iop``).
    z = ipp[2] + dicom_rt.sinal_normal_iop(rd) * offsets
    y = ipp[1] + psr * np.arange(int(rd.Rows))
    x = ipp[0] + psc * np.arange(int(rd.Columns))
    return z, y, x


def _eixos_de_rd(rd) -> tuple:
    """(z, y, x) CRESCENTES da grade de um RT Dose, sem carregar um pixel.

    Mesma geometria de ``grade_de_rd`` (via ``_eixos_brutos_de_rd``) e mesma
    normalização de sentido que ``_crescente`` aplica lá — só que aqui nos
    eixos, para montar a grade união da soma sem materializar a dose.
    """
    z, y, x = _eixos_brutos_de_rd(rd)
    if len(z) > 1 and z[0] > z[-1]:
        z = z[::-1]
    if len(y) > 1 and y[0] > y[-1]:
        y = y[::-1]
    if len(x) > 1 and x[0] > x[-1]:
        x = x[::-1]
    return z, y, x


def _crescente(g: GradeDose) -> GradeDose:
    """Garante eixos crescentes (inverte o volume no eixo se necessário)."""
    if len(g.z) > 1 and g.z[0] > g.z[-1]:
        g = GradeDose(g.dose[::-1], g.z[::-1], g.y, g.x)
    if len(g.y) > 1 and g.y[0] > g.y[-1]:
        g = GradeDose(g.dose[:, ::-1], g.z, g.y[::-1], g.x)
    if len(g.x) > 1 and g.x[0] > g.x[-1]:
        g = GradeDose(g.dose[:, :, ::-1], g.z, g.y, g.x[::-1])
    return g


def _interp_eixo(vol: np.ndarray, src: np.ndarray, tgt: np.ndarray,
                 axis: int) -> np.ndarray:
    """Interpolação linear ao longo de ``axis`` (0 fora do domínio de ``src``)."""
    vol = np.moveaxis(vol, axis, 0)
    n = vol.shape[0]
    if n == 1:
        # Um único plano no eixo: replica onde |tgt - src| for pequeno o suficiente.
        idx = np.where(np.isclose(tgt, src[0]), 0.0, -1.0)
    else:
        idx = np.interp(tgt, src, np.arange(n), left=-1.0, right=-1.0)
    out = np.zeros((len(tgt),) + vol.shape[1:], dtype=vol.dtype)
    val = idx >= 0
    if val.any():
        i0 = np.clip(np.floor(idx[val]).astype(int), 0, n - 1)
        i1 = np.clip(i0 + 1, 0, n - 1)
        frac = (idx[val] - i0).reshape((-1,) + (1,) * (vol.ndim - 1)).astype(vol.dtype)
        out[val] = vol[i0] * (1 - frac) + vol[i1] * frac
    return np.moveaxis(out, 0, axis)


def _reamostrar(g: GradeDose, Z, Y, X) -> np.ndarray:
    """Reamostra a grade ``g`` para os eixos (Z, Y, X) via trilinear separável."""
    v = _interp_eixo(g.dose, g.z, Z, 0)
    v = _interp_eixo(v, g.y, Y, 1)
    v = _interp_eixo(v, g.x, X, 2)
    return v


def _grade_uniao(eixos: list) -> tuple:
    """(Z, Y, X) da grade comum: união dos eixos, na resolução do primeiro."""
    z0, y0, x0 = eixos[0]
    dz = float(np.min(np.diff(z0))) if len(z0) > 1 else 1.0
    dy = float(y0[1] - y0[0]) if len(y0) > 1 else 1.0
    dx = float(x0[1] - x0[0]) if len(x0) > 1 else 1.0
    Z = np.arange(min(e[0].min() for e in eixos),
                  max(e[0].max() for e in eixos) + dz / 2, dz)
    Y = np.arange(min(e[1].min() for e in eixos),
                  max(e[1].max() for e in eixos) + dy / 2, dy)
    X = np.arange(min(e[2].min() for e in eixos),
                  max(e[2].max() for e in eixos) + dx / 2, dx)
    return Z, Y, X


def _acumular(Z, Y, X, grades) -> GradeDose:
    """Reamostra e soma ``grades`` (Gy) na grade comum (Z, Y, X).

    ``grades`` é consumido uma de cada vez — passe um gerador e cada grade é
    liberada assim que entra no total, antes de a próxima ser carregada.
    """
    total = np.zeros((len(Z), len(Y), len(X)), dtype=np.float32)
    for g in grades:
        total += _reamostrar(g, Z, Y, X)
    return GradeDose(total, Z, Y, X)


def somar(grades: list) -> GradeDose:
    """Soma (Gy) as grades numa grade comum = união das grades na resolução da 1ª.

    Exige todas as grades já carregadas. Para somar RT Dose direto do disco use
    ``somar_rds``, que carrega uma de cada vez.

    Levanta ``ValueError`` se a lista estiver vazia.
    """
    if not grades:
        raise ValueError("Nenhuma grade de dose para somar.")
    if len(grades) == 1:
        return grades[0]

    Z, Y, X = _grade_uniao([(g.z, g.y, g.x) for g in grades])
    return _acumular(Z, Y, X, grades)


def somar_rds(rds: list) -> GradeDose:
    """Soma uma lista de RT Dose, carregando UMA grade de cada vez.

    A grade união é montada só com os cabeçalhos (``_eixos_de_rd``), e as doses
    entram por um gerador — cada uma é liberada antes de a próxima ser carregada.
    Materializar as quatro grades antes de somar — o que ``somar`` recebe pronto
    — custava 5,8 GB de pico no paciente de 4 planos. O resultado é o mesmo:
    mesma grade união, mesma ordem de soma.

    Levanta ``ValueError`` se a lista estiver vazia.
    """
    if not rds:
        raise ValueError("Nenhuma grade de dose para somar.")
    if len(rds) == 1:
        return grade_de_rd(rds[0])

    Z, Y, X = _grade_uniao([_eixos_de_rd(rd) for rd in rds])
    return _acumular(Z, Y, X, (grade_de_rd(rd) for rd in rds))
