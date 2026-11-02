"""Série de TC completa do paciente: volume 3D e cortes (MPR).

Ao contrário do ficha-dash (que aceitava um único corte só para os metadados),
o ISOCENTRO carrega **todos** os cortes da TC, empilha o volume em HU e gera
cortes axial/sagital/coronal navegáveis, com os contornos do RT Struct
sobrepostos no corte axial.
"""

from __future__ import annotations

import logging

import numpy as np
from PIL import Image, ImageDraw

from isocentro.dicom import dicom_rt

_LOG = logging.getLogger(__name__)

def montar_series(grupos: dict[str, list]) -> list["CTSerie"]:
    """Uma ``CTSerie`` por grupo de cortes (``leitura.cortes_de_tc``), na ordem dele.

    Suporta múltiplas tomografias do mesmo paciente (ex.: TC de planejamento
    diferente por sítio). **Esvazia o dicionário**: cada grupo sai dele ao
    virar série, e os datasets da TC já montada não esperam as outras — parte
    do que levou o caso Elekta de 4,4 para 3,6 GB de pico (22/10/2026).
    """
    return [CTSerie(grupos.pop(uid)) for uid in list(grupos)]


class CTSerie:
    """Volume de TC empilhado em HU, com geometria para gerar os cortes."""

    def __init__(self, slices: list):
        slices = sorted(slices, key=lambda s: float(s.ImagePositionPatient[2]))
        s0 = slices[0]
        self._n_axial = len(slices)
        self.rows = int(s0.Rows)
        self.cols = int(s0.Columns)
        self.ipp0 = [float(v) for v in s0.ImagePositionPatient]
        self.psr = float(s0.PixelSpacing[0])
        self.psc = float(s0.PixelSpacing[1])
        # ImageOrientationPatient define o sinal da conversão pixel↔coordenada.
        # iop[0] = componente X da direção-linha (±1): −1 para FFS/HFP (x inverte).
        # iop[4] = componente Y da direção-coluna (±1): −1 para HFP/FFP (y inverte).
        iop = getattr(s0, "ImageOrientationPatient", [1, 0, 0, 0, 1, 0])
        self.iop_fx = float(iop[0])
        self.iop_gy = float(iop[4])
        self.psc_eff = self.iop_fx * self.psc   # espaçamento de coluna com sinal
        self.psr_eff = self.iop_gy * self.psr   # espaçamento de linha com sinal
        self.zs = np.array([float(s.ImagePositionPatient[2]) for s in slices])
        difs = np.diff(self.zs)
        self.dz = float(np.median(difs)) if len(difs) else float(getattr(s0, "SliceThickness", 1))
        if self.dz == 0:
            self.dz = float(getattr(s0, "SliceThickness", 1) or 1)

        slope = float(getattr(s0, "RescaleSlope", 1))
        inter = float(getattr(s0, "RescaleIntercept", 0))
        # Converte para HU corte a corte, direto no volume final. Empilhar tudo
        # em float32 antes (np.stack + *slope + inter + astype) mantinha quatro
        # cópias do volume inteiro vivas ao mesmo tempo: ~800 MB de pico para
        # um volume de 107 MB. Aqui o pico é o volume + um corte.
        self.volume = np.empty((self._n_axial, self.rows, self.cols), dtype=np.int16)
        for i, s in enumerate(slices):
            self.volume[i] = (s.pixel_array.astype(np.float32) * slope + inter
                              ).astype(np.int16)   # (Z, rows, cols) em HU
            # O corte já está no volume; solta o array que o pydicom cacheia
            # e o PixelData cru. Sem isto, os datasets segurariam mais duas
            # cópias de tudo até o fim da montagem. Daqui para baixo só se lê
            # cabeçalho.
            dicom_rt.soltar_cache_pixels(s)
            del s.PixelData

        self.wl_padrao = float(np.ravel(getattr(s0, "WindowCenter", 40))[0])
        self.ww_padrao = float(np.ravel(getattr(s0, "WindowWidth", 400))[0])
        self.frame_uid = str(getattr(s0, "FrameOfReferenceUID", "") or "")
        self.paciente = dicom_rt.dados_paciente(s0)
        self.descricao = str(getattr(s0, "StudyDescription", "") or "")
        # Descrição da série: em 4DCT nomeia as fases (ex.: "Ave(7) 20%_…_80%"),
        # de onde se deduz a janela de gating por fase.
        self.serie_descricao = str(getattr(s0, "SeriesDescription", "") or "")
        self.data_estudo = dicom_rt._formatar_data(getattr(s0, "StudyDate", ""))
        self.instituicao = str(getattr(s0, "InstitutionName", "") or "")

    # ------------------------------------------------------------------
    # Tamanhos / índices
    # ------------------------------------------------------------------
    @property
    def n_axial(self) -> int:
        return self._n_axial

    def n_cortes(self, plano: str) -> int:
        return {"Axial": self.n_axial, "Sagital": self.cols, "Coronal": self.rows}[plano]

    def indice_central(self, plano: str) -> int:
        return self.n_cortes(plano) // 2

    def indices_do_ponto(self, ponto_mm) -> dict:
        """Índice de corte de cada plano que passa pelo ponto (x, y, z) em mm.

        Mesma convenção pixel↔coordenada do render/estruturas (``psc_eff`` /
        ``psr_eff`` com sinal). Útil para abrir os cortes no isocentro.
        """
        x, y, z = float(ponto_mm[0]), float(ponto_mm[1]), float(ponto_mm[2])
        ax = int(np.argmin(np.abs(self.zs - z)))
        sag = round((x - self.ipp0[0]) / self.psc_eff) if self.psc_eff else self.cols // 2
        cor = round((y - self.ipp0[1]) / self.psr_eff) if self.psr_eff else self.rows // 2
        return {
            "Axial": int(np.clip(ax, 0, self.n_axial - 1)),
            "Sagital": int(np.clip(sag, 0, self.cols - 1)),
            "Coronal": int(np.clip(cor, 0, self.rows - 1)),
        }

    # ------------------------------------------------------------------
    # Cortes
    # ------------------------------------------------------------------
    def _plano_cinza(self, plano: str, idx: int) -> tuple[np.ndarray, tuple[float, float]]:
        """Retorna (imagem_cinza HxW, (escala_y_mm, escala_x_mm)) do corte bruto."""
        if plano == "Axial":
            idx = int(np.clip(idx, 0, self.n_axial - 1))
            arr = self.volume[idx]
            return arr, (self.psr, self.psc)
        if plano == "Sagital":
            idx = int(np.clip(idx, 0, self.cols - 1))
            # volume[:, :, x] -> (Z, rows); topo = superior (z maior).
            arr = self.volume[:, :, idx][::-1, :]
            return arr, (self.dz, self.psr)
        # Coronal
        idx = int(np.clip(idx, 0, self.rows - 1))
        arr = self.volume[:, idx, :][::-1, :]
        return arr, (self.dz, self.psc)

    def _mask_sagital(self, contornos, x_idx: int) -> np.ndarray:
        """Máscara ``(n_axial, rows)`` preenchida da seção sagital x = x_idx.

        Preenche, em cada corte Z, os intervalos entre pares de cruzamentos do
        polígono com a linha ``x = x_fix`` — cada parte da estrutura vira uma
        faixa própria, sem unir pedaços distintos.
        """
        x_fix = self.ipp0[0] + x_idx * self.psc_eff
        mask = np.zeros((self.n_axial, self.rows), dtype=bool)
        for pts in contornos:
            ri = int(np.argmin(np.abs(self.zs - float(pts[0, 2]))))
            row_img = self.n_axial - 1 - ri
            ys = _interseccoes_poligono(pts[:, :2], x_fix, eixo=0)
            for i in range(0, len(ys) - 1, 2):
                c0 = int(np.clip(round((ys[i] - self.ipp0[1]) / self.psr_eff), 0, self.rows - 1))
                c1 = int(np.clip(round((ys[i + 1] - self.ipp0[1]) / self.psr_eff), 0, self.rows - 1))
                lo, hi = (c0, c1) if c0 <= c1 else (c1, c0)
                mask[row_img, lo:hi + 1] = True
        return mask

    def _mask_coronal(self, contornos, y_idx: int) -> np.ndarray:
        """Máscara ``(n_axial, cols)`` preenchida da seção coronal y = y_idx."""
        y_fix = self.ipp0[1] + y_idx * self.psr_eff
        mask = np.zeros((self.n_axial, self.cols), dtype=bool)
        for pts in contornos:
            ri = int(np.argmin(np.abs(self.zs - float(pts[0, 2]))))
            row_img = self.n_axial - 1 - ri
            xs = _interseccoes_poligono(pts[:, :2], y_fix, eixo=1)
            for i in range(0, len(xs) - 1, 2):
                c0 = int(np.clip(round((xs[i] - self.ipp0[0]) / self.psc_eff), 0, self.cols - 1))
                c1 = int(np.clip(round((xs[i + 1] - self.ipp0[0]) / self.psc_eff), 0, self.cols - 1))
                lo, hi = (c0, c1) if c0 <= c1 else (c1, c0)
                mask[row_img, lo:hi + 1] = True
        return mask

    def _mascara_corpo(self, plano: str, idx: int, rs,
                       z_axial: float | None) -> "np.ndarray | None":
        """Máscara do que é PACIENTE neste corte, ou ``None`` se não der para saber.

        É o contorno EXTERNAL MAIS o que estiver encostado na pele e receba dose
        de verdade — o bólus. Serve para duas coisas: pintar o fundo fora do
        corpo e recortar o colorwash de isodose, que sem isso vaza para o ar (a
        grade de dose do TPS não para na pele) e a ficha mostrava isodose
        flutuando ao lado do paciente.

        ``None`` quando o corpo não está contornado ALI: aí a TC sai crua e a
        dose sai inteira, em vez de a fatia virar um retângulo vazio. "Ali" é
        fora da extensão em z do corpo — buraco no meio dela é remendado com a
        fatia contornada mais próxima (ver ``_herdar_lacunas_z``).
        """
        rois = list(_contornos_por_roi(rs).values())
        externos = [r["contornos"] for r in rois if r["tipo"] == "EXTERNAL"]
        bolus = [r["contornos"] for r in rois
                 if r["tipo"] != "EXTERNAL" and _eh_bolus(r)]
        # Quem define o corpo é o EXTERNAL; o bólus só ACRESCENTA a ele. Sem
        # EXTERNAL não há máscara: uma feita de bólus sozinho pintaria de fundo
        # tudo fora dele — o corte inteiro menos um retanguinho.
        if not externos:
            return None

        if plano == "Axial":
            if z_axial is None:
                return None
            alvo = self._z_do_corpo(externos, z_axial)
            if alvo is None:
                return None
            z_alvo, tol = alvo
            mask = Image.new("1", (self.cols, self.rows), 0)
            d = ImageDraw.Draw(mask)

            def desenhar(contornos) -> bool:
                achou = False
                for pts in contornos:
                    if abs(float(pts[0, 2]) - z_alvo) > tol:
                        continue
                    col = (pts[:, 0] - self.ipp0[0]) / self.psc_eff
                    row = (pts[:, 1] - self.ipp0[1]) / self.psr_eff
                    d.polygon(list(zip(col, row)), fill=1)
                    achou = True
                return achou

            # O que manda é o EXTERNAL: bólus sem corpo contornado (o TPS não
            # contorna o corpo de ponta a ponta) não vale como máscara — era
            # assim que "o axial sumia", quase todo de fundo.
            tem_corpo = False
            for c in externos:
                tem_corpo = desenhar(c) or tem_corpo   # sem curto-circuito
            if not tem_corpo:
                return None
            for c in bolus:
                desenhar(c)
            return np.array(mask, dtype=bool)

        if plano == "Sagital":
            x_idx = int(np.clip(idx, 0, self.cols - 1))
            m = np.zeros((self.n_axial, self.rows), dtype=bool)
            for contornos in externos + bolus:
                m |= self._mask_sagital(contornos, x_idx)
        else:
            y_idx = int(np.clip(idx, 0, self.rows - 1))
            m = np.zeros((self.n_axial, self.cols), dtype=bool)
            for contornos in externos + bolus:
                m |= self._mask_coronal(contornos, y_idx)
        m = self._herdar_lacunas_z(m, externos)
        return m if m.any() else None

    def _z_do_corpo(self, externos: list, z_axial: float):
        """``(z, tolerância)`` do contorno de corpo que vale para o corte ``z_axial``.

        Normalmente é o próprio ``z_axial``, com a tolerância de meia fatia. Onde
        o BODY tem BURACO (o do Monaco pula até 15 mm em z), devolve a fatia
        contornada mais próxima — o mesmo remendo que ``_herdar_lacunas_z`` faz
        no sagital/coronal e que ``corpo3d._voxelizar`` faz na malha. Sem ele o
        corte caía no ``None``, e ``None`` significa "não recorta nada": a
        isodose voltava a aparecer no ar justamente nos cortes do buraco.

        ``None`` quando ``z_axial`` está FORA da extensão do corpo: ali não há o
        que herdar — acima da cabeça é ar de verdade, e a TC crua é o certo.
        """
        zs = sorted({float(pts[0, 2]) for c in externos for pts in c})
        if not zs:
            return None
        if any(abs(z - z_axial) <= abs(self.dz) for z in zs):
            return z_axial, abs(self.dz)
        if not zs[0] < z_axial < zs[-1]:
            return None
        # Herda uma fatia inteira: a tolerância é estreita para não misturar a
        # vizinha dela no caminho.
        return min(zs, key=lambda z: abs(z - z_axial)), 1e-3

    def _herdar_lacunas_z(self, m: "np.ndarray", externos: list) -> "np.ndarray":
        """Nas fatias SEM contorno de corpo, repete a fatia contornada mais próxima.

        ``_mask_sagital``/``_mask_coronal`` preenchem só a linha da imagem mais
        próxima de cada z contornado. O BODY não vem obrigatoriamente em toda
        fatia — no Monaco há buracos de até 15 mm em z —, e as linhas do meio
        ficavam vazias: como esta máscara agora também RECORTA o colorwash, a
        isodose saía listrada no sagital/coronal. É o mesmo remendo que a malha
        3D faz em ``corpo3d._voxelizar``.

        Fora da extensão em z do corpo nada é preenchido: ali é ar de verdade.
        """
        linhas = set()
        for contornos in externos:
            for pts in contornos:
                ri = int(np.argmin(np.abs(self.zs - float(pts[0, 2]))))
                linhas.add(self.n_axial - 1 - ri)
        if not linhas:
            return m
        conhecidas = np.array(sorted(linhas))
        for r in range(int(conhecidas[0]), int(conhecidas[-1]) + 1):
            if r in linhas:
                continue
            m[r] = m[int(conhecidas[np.abs(conhecidas - r).argmin()])]
        return m


def _eh_bolus(roi: dict) -> bool:
    """True para a ROI de bólus — o material posto sobre a pele.

    Dose FORA do contorno externo só é real onde há bólus; no resto é a grade do
    TPS passando pelo ar. Aceita o tipo DICOM e o nome, porque nem todo TPS
    preenche ``RTROIInterpretedType`` (o Monaco só usa EXTERNAL/ORGAN/PTV/
    SUPPORT/MARKER).
    """
    return (str(roi.get("tipo", "")).upper() == "BOLUS"
            or "bolus" in str(roi.get("nome", "")).lower()
            or "bólus" in str(roi.get("nome", "")).lower())


# Sentinela de cache: já computado e não há colorwash a mostrar (dose ~0 ou
# falha). Distingue "ainda não calculei" (atributo ausente) de "calculei e deu
# nada" (este valor) — senão um RD sem isodose recomputaria a cada corte.
_SEM_ISODOSE = object()


def _dose_pct_grade(rd, dose_ref: float | None = None):
    """Grade 3D de dose normalizada em % (tupla), ou None. Cacheada no ``rd``.

    ``dose_ref`` (Gy): dose de referência do 100% — a PRESCRIÇÃO do plano. É a
    convenção do TPS e a única estável: normalizar pelo máximo da grade faz o
    100% seguir o ponto quente, e aí a mesma faixa de % vale doses diferentes em
    cada plano (e outra ainda na soma). Sem ``dose_ref``, cai no máximo.

    Roda a cada corte navegado com isodose ligada. Sem cache, um RT Dose grande
    custa ~0,6 s e ~1 GB transitório por corte — e re-decodifica os pixels do
    zero se a ficha soma já tinha soltado o cache do pydicom. O resultado só
    depende do RD e da referência, então fica guardado no RD junto dela.

    ``None`` tem dois motivos, de propósito distintos: dose ~0 (nada a mostrar,
    caso legítimo e silencioso) e falha ao ler os pixels — que antes sumia da
    tela sem rastro nenhum e agora vai para o log.
    """
    ref = float(dose_ref) if dose_ref else None
    cache = getattr(rd, "_isocentro_dose_pct", None)
    if cache is not None:
        if cache is _SEM_ISODOSE:
            return None
        ref_cache, grade = cache
        if ref_cache == ref:
            return grade

    try:
        escala = float(getattr(rd, "DoseGridScaling", 1.0))
        dose_raw = rd.pixel_array.astype(np.float32)  # (nz, ny, nx)
        dose_max = float(dose_raw.max()) * escala
        if dose_max < 1e-9:
            rd._isocentro_dose_pct = _SEM_ISODOSE   # sem dose: não é erro
            return None
        # 100% = prescrição (ou o máximo da grade, na falta dela).
        dose_100 = ref if (ref and ref > 1e-9) else dose_max
        z0 = float(rd.ImagePositionPatient[2])
        offsets = np.array([float(o) for o in rd.GridFrameOffsetVector])
        rd_ipp = [float(v) for v in rd.ImagePositionPatient]
        # Espaçamento COM SINAL (o IOP da grade de dose, não o da TC): em
        # decúbito ventral x/y diminuem a partir do IPP. Com o sinal positivo
        # fixo, (px − ipp)/ps dava índice negativo em toda a grade, o clip
        # prendia tudo na borda e o colorwash sumia — a dose "não aparecia".
        _sr, _sc = dicom_rt.sinais_iop(rd)
        rd_psr = float(rd.PixelSpacing[0]) * _sr
        rd_psc = float(rd.PixelSpacing[1]) * _sc
        # E o mesmo vale para o Z: os offsets de corte andam pela NORMAL do
        # plano (linha × coluna), que no FFS aponta para −Z. Somando sempre, a
        # grade ficava uma grade inteira fora do paciente e o colorwash sumia —
        # o mesmo defeito que o parágrafo acima descreve em x/y, e que ficou
        # neste eixo por mais tempo porque só aparece em decúbito com IOP
        # espelhado. Medido no caso 9000021ANA (21/08/2026).
        resultado = (dose_raw * escala / dose_100 * 100.0,
                     z0 + dicom_rt.sinal_normal_iop(rd) * offsets,
                     rd_ipp, rd_psr, rd_psc)
    except Exception:  # noqa: BLE001
        _LOG.exception("Isodose: RT Dose ilegível — colorwash omitido")
        rd._isocentro_dose_pct = _SEM_ISODOSE
        return None

    rd._isocentro_dose_pct = (ref, resultado)
    # dose_pct já carrega o dado; solta o pixel_array que o pydicom cacheia para
    # não segurar as duas cópias (~mesma memória residente que antes, sem o RD).
    dicom_rt.soltar_cache_pixels(rd)
    return resultado


def maximo_pct(grade) -> float:
    """Maior valor da grade de dose, em % da referência (o ponto quente).

    ``grade`` é a tupla do colorwash (``_dose_pct_grade``/``tupla_dose``); 0.0
    quando não há dose. É o topo natural da faixa quando ela é lida em cGy: em %
    a faixa para na prescrição, e o que passa dela fica invisível."""
    if not grade:
        return 0.0
    try:
        return float(np.max(grade[0]))
    except Exception:  # noqa: BLE001 — sem dose legível, sem ponto quente
        return 0.0


def tupla_dose(gradedose, dose_ref: float | None = None):
    """Converte uma ``dose3d.GradeDose`` (Gy) para o formato do colorwash.

    ``dose_ref`` (Gy): dose do 100% — na dose combinada, a SOMA das prescrições
    dos planos combinados. Sem ela, cai no máximo da grade; e aí o 100% pula do
    ponto quente de um plano para o da soma, o limiar da faixa sobe sozinho e o
    colorwash da soma ENCOLHE, parecendo que a soma não foi aplicada.
    Retorna None se dose ~0.
    """
    m = float(gradedose.dose.max())
    if m < 1e-9:
        return None
    if dose_ref and float(dose_ref) > 1e-9:
        m = float(dose_ref)
    dose_pct = (gradedose.dose.astype(np.float32) / m * 100.0)
    dx = float(gradedose.x[1] - gradedose.x[0]) if len(gradedose.x) > 1 else 1.0
    dy = float(gradedose.y[1] - gradedose.y[0]) if len(gradedose.y) > 1 else 1.0
    ipp = [float(gradedose.x[0]), float(gradedose.y[0]), float(gradedose.z[0])]
    return dose_pct, np.asarray(gradedose.z, dtype=float), ipp, dy, dx


def _amostrar_axial(grade, ipp0, psr, psc, rows, cols, z):
    """Array (rows, cols) % dose para o corte axial em z."""
    d3, zs, ripp, rpsr, rpsc = grade
    nz, ny, nx = d3.shape
    dz = abs(float(zs[1] - zs[0])) if len(zs) > 1 else 5.0
    fi = int(np.argmin(np.abs(zs - z)))
    if abs(float(zs[fi]) - z) > dz * 1.5:
        return None
    px = ipp0[0] + np.arange(cols, dtype=np.float32) * psc
    py = ipp0[1] + np.arange(rows, dtype=np.float32) * psr
    dc = np.clip(np.round((px - ripp[0]) / rpsc).astype(np.int32), 0, nx - 1)
    dr = np.clip(np.round((py - ripp[1]) / rpsr).astype(np.int32), 0, ny - 1)
    return d3[fi][dr[:, None], dc[None, :]]


def _amostrar_sagital(grade, ipp0, psr, psc, zs, ct_rows, x_idx):
    """Array (n_axial, ct_rows) % dose para o corte sagital em x_idx."""
    d3, zs_dose, ripp, rpsr, rpsc = grade
    nz, ny, nx = d3.shape
    x_fix = ipp0[0] + x_idx * psc
    dc = int(np.clip(round((x_fix - ripp[0]) / rpsc), 0, nx - 1))
    zs_img = zs[::-1]  # linha 0 da imagem = z mais alto
    fi_arr = np.argmin(np.abs(zs_dose[:, None] - zs_img[None, :]), axis=0)
    py = ipp0[1] + np.arange(ct_rows, dtype=np.float32) * psr
    dr_arr = np.clip(np.round((py - ripp[1]) / rpsr).astype(np.int32), 0, ny - 1)
    return d3[fi_arr[:, None], dr_arr[None, :], dc]


def _amostrar_coronal(grade, ipp0, psr, psc, zs, ct_cols, y_idx):
    """Array (n_axial, ct_cols) % dose para o corte coronal em y_idx."""
    d3, zs_dose, ripp, rpsr, rpsc = grade
    nz, ny, nx = d3.shape
    y_fix = ipp0[1] + y_idx * psr
    dr = int(np.clip(round((y_fix - ripp[1]) / rpsr), 0, ny - 1))
    zs_img = zs[::-1]
    fi_arr = np.argmin(np.abs(zs_dose[:, None] - zs_img[None, :]), axis=0)
    px = ipp0[0] + np.arange(ct_cols, dtype=np.float32) * psc
    dc_arr = np.clip(np.round((px - ripp[0]) / rpsc).astype(np.int32), 0, nx - 1)
    return d3[fi_arr[:, None], dr, dc_arr[None, :]]


def _interseccoes_poligono(pts_xy: np.ndarray, coord: float, eixo: int) -> list:
    """Valores do outro eixo onde o polígono 2D cruza a linha coord no eixo dado."""
    result = []
    n = len(pts_xy)
    for i in range(n):
        a, b = pts_xy[i], pts_xy[(i + 1) % n]
        va, vb = float(a[eixo]), float(b[eixo])
        if (va <= coord <= vb) or (vb <= coord <= va):
            dv = vb - va
            if abs(dv) > 1e-6:
                t = (coord - va) / dv
                outro = 1 - eixo
                result.append(float(a[outro]) + t * (float(b[outro]) - float(a[outro])))
    return sorted(result)


def _pontos_contorno(c) -> np.ndarray:
    """(N, 3) float do ``ContourData`` de um item de ContourSequence.

    Lê o elemento CRU e converte com numpy. O ContourData é um DS — texto
    ``"1.2\\3.4\\..."`` — e o caminho normal do pydicom monta um MultiValue
    validando valor a valor: ~7x mais lento para o mesmo resultado, e um RS de
    200 mil pontos custava ~1,2 s só nisso. ``get_item`` devolve o elemento sem
    disparar essa conversão; se ele já veio convertido, usa o valor como está.
    """
    el = c.get_item("ContourData")
    v = getattr(el, "value", None)
    if isinstance(v, (bytes, bytearray)):
        texto = bytes(v).decode("ascii")
        pts = np.array(texto.split("\\"), dtype=float)
    else:   # já convertido pelo pydicom (ou elemento ausente)
        pts = np.asarray(c.ContourData if v is None else v, dtype=float)
    return pts.reshape(-1, 3)


def _contornos_por_roi(rs) -> dict:
    """{num_roi: {nome, tipo, cor, contornos}} a partir do RT Struct.

    ``contornos`` já vem como lista de arrays ``(N, 3)`` de float — não como os
    elementos DICOM crus. O ``ContourData`` é um DS (string) e o pydicom o
    reconverte a CADA acesso: com os contornos ligados, um corte custava ~960 ms
    e 280 MB, quase tudo em revalidar as mesmas strings, e isso rodava a cada
    movimento do slider.

    O resultado fica cacheado no próprio RS — a vida do cache é a do dataset, e
    o RS não muda depois de carregado.
    """
    cache = getattr(rs, "_isocentro_rois", None)
    if cache is not None:
        return cache

    from isocentro.dicom.corpo3d import _NOMES_BODY   # mesma lista de nomes de corpo (fonte única)
    nomes = {int(r.ROINumber): str(r.ROIName) for r in rs.StructureSetROISequence}
    tipos = {
        int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", ""))
        for o in getattr(rs, "RTROIObservationsSequence", [])
    }

    def _tipo(num: int) -> str:
        """Tipo da ROI; corpo achado pelo NOME (case-insensitive) conta como
        EXTERNAL mesmo sem a tag DICOM — assim "Body"/"body"/"BODY" mascaram o
        fundo do axial, ficam fora do desenho de estruturas e fora do DVH, igual
        ao que o SSD/3D já fazem em corpo3d."""
        t = tipos.get(num, "")
        if t == "EXTERNAL":
            return t
        return "EXTERNAL" if nomes.get(num, "").strip().upper() in _NOMES_BODY else t

    saida = {}
    for rc in getattr(rs, "ROIContourSequence", []):
        num = int(rc.ReferencedROINumber)
        cor = tuple(int(v) for v in getattr(rc, "ROIDisplayColor", [255, 0, 0]))
        contornos = []
        for c in getattr(rc, "ContourSequence", []) or []:
            # Só contorno planar fechado: o filtro era feito no render axial e
            # agora vale para todos os planos, que antes desenhavam qualquer tipo.
            geo = str(getattr(c, "ContourGeometricType", "CLOSED_PLANAR"))
            if geo not in ("CLOSED_PLANAR", ""):
                continue
            pts = _pontos_contorno(c)
            if len(pts) >= 3:            # ao menos 3 pontos (x, y, z)
                contornos.append(pts)
        saida[num] = {
            "nome": nomes.get(num, str(num)),
            "tipo": _tipo(num),
            "cor": cor,
            "contornos": contornos,
        }
    rs._isocentro_rois = saida
    return saida
