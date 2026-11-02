"""Margem entre duas ROIs (o CTV dentro do PTV), medida pela geometria.

Por que existe: no estudo de hazard do COURT-2026 (JACMP, doi
10.1002/acm2.70759), 2 de 5 físicos nem avaliaram a margem do PTV, e quem
avaliou acertou de 13% a 63% dos erros semeados. Margem é geometria: o código
mede, e a pessoa decide. Este módulo NÃO compara com protocolo nenhum e não
diz se a margem está certa (isso é do módulo Plano); só devolve os números,
com a precisão de cada um ao lado.

Convenção (sistema do paciente DICOM, LPS), a mesma do ``ContourData``:

- **+x = esquerda** do paciente, −x = direita;
- **+y = posterior**, −y = anterior;
- **+z = superior**, −z = inferior.

A margem "esquerda" é a distância, ao longo de +x, da borda esquerda da ROI
interna até a borda esquerda da externa; as outras cinco, idem no seu sentido.

Método, e por que este:

1. As duas ROIs são rasterizadas numa **rede comum**: passo ``resolucao_mm``
   em x e y, e em z os próprios planos de corte (a espessura sai do
   espaçamento dos contornos). A rede é ancorada em múltiplos do passo, então
   duas ROIs rasterizadas em separado caem nos mesmos voxels.
2. Cada corte é preenchido pela regra **par-ímpar** sobre TODAS as arestas dos
   polígonos daquele corte. É o mesmo resultado do XOR de
   ``dicom/dvh._mascara_estrutura`` (ilha e buraco no mesmo plano), sem o PIL,
   que a camada ``rt`` não pode importar.
3. Margem por direção = o **mínimo**, sobre todas as linhas da grade naquele
   eixo, do número de voxels da externa que sobram além do último voxel da
   interna, vezes o passo. Por que o mínimo: se a externa é a interna expandida
   (soma de Minkowski), toda linha tem pelo menos a margem da expansão, e a
   linha cuja normal aponta naquele eixo tem exatamente ela. A média ou a
   mediana diriam "folga típica", que não é o que o protocolo chama de margem.
4. Margem mínima 3D = a menor distância entre os voxels da interna e os voxels
   FORA da externa (distância entre as caixas dos voxels, que no eixo dá o
   mesmo número do passo 3). Procura-se por deslocamentos em ordem crescente
   de distância, limitada pela menor margem por direção — sem scipy, que não
   é dependência do projeto.

A alternativa de medir direto nos polígonos foi descartada: entre cortes não
há polígono, e a direção superior/inferior ficaria sem método. Na rede, as
seis direções saem do mesmo raciocínio — e a precisão de cada uma é declarada:
``resolucao_mm`` no plano, a **espessura de corte** em superior/inferior (a
borda de uma ROI só existe de corte em corte; nenhuma conta recupera o que
está entre eles).

Interna fora da externa não vira margem negativa calada: a saída traz a
fração do volume interno que fica fora, e a direção em que a interna vaza
fica SEM número (``None``), com o aviso dizendo qual.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np

DIRECOES = ("direita", "esquerda", "anterior", "posterior", "superior", "inferior")

# Direção -> (eixo do volume (z, y, x), sentido). +x esquerda, +y posterior,
# +z superior (LPS).
_EIXO = {
    "direita": (2, -1), "esquerda": (2, +1),
    "anterior": (1, -1), "posterior": (1, +1),
    "inferior": (0, -1), "superior": (0, +1),
}

Contornos = Sequence[np.ndarray]


@dataclass(frozen=True)
class MargemMedida:
    """O que se mediu entre a ROI interna e a externa. Sem veredito.

    ``margens_mm`` e ``precisao_mm`` são por direção (``DIRECOES``); a
    ``precisao_mm`` tem também a chave ``"3d"``. Margem ``None`` = a interna
    sai da externa naquela direção (ver ``fracao_fora``), ou, em
    superior/inferior, que os contornos ocupam um plano só; os ``avisos``
    dizem qual.
    """
    margens_mm: Mapping[str, float | None]
    minima_3d_mm: float | None
    precisao_mm: Mapping[str, float]
    resolucao_mm: float
    espessura_corte_mm: float
    contida: bool
    fracao_fora: float
    volume_interna_cm3: float
    volume_externa_cm3: float
    avisos: tuple[str, ...]


@dataclass(frozen=True)
class ParCandidato:
    """Uma ROI que cabe (quase) inteira dentro de outra, achada pela geometria."""
    interna: str
    externa: str
    fracao_dentro: float
    volume_interna_cm3: float
    volume_externa_cm3: float


@dataclass(frozen=True)
class _Rede:
    passo: float      # x e y, mm
    espessura: float  # z, mm
    zref: float       # z do plano k = 0


@dataclass(frozen=True)
class _Bloco:
    """Máscara de uma ROI num pedaço da rede, a partir do índice (k0, i0, j0)."""
    k0: int
    i0: int
    j0: int
    m: np.ndarray

    @property
    def fim(self) -> tuple[int, int, int]:
        return (self.k0 + self.m.shape[0], self.i0 + self.m.shape[1],
                self.j0 + self.m.shape[2])


def _poligonos(contornos: Iterable) -> list[np.ndarray]:
    # Menos de 3 pontos é POINT ou linha aberta: não cerca área nenhuma.
    polis = [np.asarray(c, dtype=float).reshape(-1, 3) for c in contornos]
    return [p for p in polis if len(p) >= 3]


def _zs(polis: Iterable[np.ndarray]) -> np.ndarray:
    # Média, e não o primeiro ponto: o plano é o mesmo, e a média não herda o
    # ruído de um vértice só.
    return np.array([float(p[:, 2].mean()) for p in polis])


def _espessura(zs: np.ndarray) -> float | None:
    """Espaçamento entre planos de contorno: a mediana das diferenças.

    A mediana, e não o mínimo: dois planos quase iguais (arredondamento do
    TPS) dariam espessura zero; e um corte pulado no meio da ROI não deve
    dobrar a espessura do resto. Mesma conta (e mesmo arredondamento) de
    ``dicom/dvh._espessura_dos_contornos``, que a R-58 junta a esta.
    """
    u = np.unique(np.round(zs, 3))
    if len(u) < 2:
        return None
    return float(np.median(np.diff(u)))


def _rede(todas: Sequence[list[np.ndarray]], resolucao_mm: float,
          espessura_mm: float | None) -> _Rede:
    """A rede comum, recusando o espaçamento que ela não representa.

    A rede tem planos a passo FIXO. Com a TC de espaçamento misto (1,25 mm num
    trecho, 2,5 no outro), dois contornos caem no mesmo plano e o par-ímpar
    os apaga um contra o outro — o volume encolhe e a margem SI vira zero, sem
    erro nenhum. O mesmo com uma ``espessura_mm`` que não bate com os
    contornos (a ``SliceThickness`` da TC não é o espaçamento). Recusar é
    melhor que um número que parece medido.
    """
    if not resolucao_mm > 0:
        raise ValueError("resolucao_mm tem de ser positiva")
    zs = np.concatenate([_zs(p) for p in todas if p]) if any(todas) else np.array([])
    if not len(zs):
        raise ValueError("ROI sem contorno: não há o que medir")
    medida = _espessura(zs)
    if espessura_mm is not None and medida is not None \
            and abs(espessura_mm - medida) > 0.01 * medida:
        raise ValueError(f"espessura_mm={espessura_mm} não bate com o espaçamento "
                         f"dos contornos ({medida:.3f} mm); ela só serve para "
                         f"contornos num plano só")
    esp = espessura_mm if espessura_mm is not None else medida
    if esp is None or not esp > 0:
        raise ValueError("a espessura de corte não se deduz de um plano só; "
                         "passe espessura_mm")
    u = np.unique(np.round(zs, 3))
    q = (u - u[0]) / esp
    if np.any(np.abs(q - np.rint(q)) > 0.25) or len(np.unique(np.rint(q))) < len(u):
        raise ValueError(f"espaçamento irregular entre os planos de contorno "
                         f"(passo típico {esp:.3f} mm): numa rede de passo fixo "
                         f"dois cortes cairiam no mesmo plano")
    return _Rede(float(resolucao_mm), float(esp), float(u[0]))


def _plano(polis: list[np.ndarray], i0: int, j0: int, ni: int, nj: int,
           passo: float) -> np.ndarray:
    """Preenche um corte pela regra par-ímpar sobre todas as arestas dele.

    O voxel (i, j) tem centro em ((j0+j)·passo, (i0+i)·passo). Para cada linha
    y, as arestas que a cruzam (regra semiaberta: o vértice exatamente na
    linha conta uma vez só) marcam o primeiro voxel à direita do cruzamento; a
    soma acumulada ao longo da linha, módulo 2, é dentro/fora.
    """
    a = np.vstack([p[:, :2] for p in polis])
    b = np.vstack([np.roll(p[:, :2], -1, axis=0) for p in polis])
    ys = (i0 + np.arange(ni)) * passo
    ay, by = a[:, 1:2], b[:, 1:2]
    cruza = ((ay <= ys) & (ys < by)) | ((by <= ys) & (ys < ay))
    e, r = np.nonzero(cruza)
    t = (ys[r] - a[e, 1]) / (b[e, 1] - a[e, 1])
    xc = a[e, 0] + t * (b[e, 0] - a[e, 0])
    jc = np.clip(np.ceil(xc / passo - j0), 0, nj).astype(np.intp)
    viradas = np.zeros((ni, nj + 1), dtype=np.int32)
    np.add.at(viradas, (r, jc), 1)
    return (np.cumsum(viradas[:, :nj], axis=1) & 1).astype(bool)


def _rasterizar(polis: list[np.ndarray], rede: _Rede) -> _Bloco | None:
    if not polis:
        return None
    pts = np.vstack(polis)
    p = rede.passo
    j0, j1 = math.floor(pts[:, 0].min() / p), math.ceil(pts[:, 0].max() / p)
    i0, i1 = math.floor(pts[:, 1].min() / p), math.ceil(pts[:, 1].max() / p)
    ks = np.rint((_zs(polis) - rede.zref) / rede.espessura).astype(int)
    k0 = int(ks.min())
    m = np.zeros((int(ks.max()) - k0 + 1, i1 - i0 + 1, j1 - j0 + 1), dtype=bool)
    for k in np.unique(ks):
        doplano = [poli for poli, kk in zip(polis, ks) if kk == k]
        m[k - k0] = _plano(doplano, i0, j0, m.shape[1], m.shape[2], p)
    return _Bloco(k0, i0, j0, m)


def _no_volume(b: _Bloco, ini: tuple[int, int, int],
               forma: tuple[int, int, int]) -> np.ndarray:
    v = np.zeros(forma, dtype=bool)
    k, i, j = (b.k0 - ini[0], b.i0 - ini[1], b.j0 - ini[2])
    nk, ni, nj = b.m.shape
    v[k:k + nk, i:i + ni, j:j + nj] = b.m
    return v


def _margem_direcao(dentro: np.ndarray, externa: np.ndarray, eixo: int,
                    sentido: int, passo: float) -> float | None:
    """Menor margem ao longo de um eixo, num sentido; ``None`` se a interna vaza.

    Em cada linha, o último voxel de cada trecho da interna é a borda; dali,
    contam-se os voxels da externa até o primeiro fora dela. O volume tem
    folga de um voxel em volta, então nenhuma linha termina dentro.
    """
    if sentido < 0:
        dentro, externa = np.flip(dentro, eixo), np.flip(externa, eixo)
    dentro = np.moveaxis(dentro, eixo, -1)
    externa = np.moveaxis(externa, eixo, -1)
    n = dentro.shape[-1]
    borda = dentro.copy()
    borda[..., :-1] &= ~dentro[..., 1:]
    if not externa[borda].all():
        return None
    # proximo_fora[..., j] = índice do primeiro voxel fora da externa a partir
    # de j (n se não houver).
    pos = np.where(externa, np.int32(n), np.arange(n, dtype=np.int32))
    proximo_fora = np.minimum.accumulate(pos[..., ::-1], axis=-1)[..., ::-1]
    j = np.nonzero(borda)[-1]
    sobra = proximo_fora[borda] - j - 1
    return float(sobra.min()) * passo


def _minima_3d(dentro: np.ndarray, externa: np.ndarray,
               passos: tuple[float, float, float], cota: float) -> float:
    """Menor distância entre os voxels da interna e os de fora da externa.

    Distância entre CAIXAS de voxel: no deslocamento (oz, oy, ox), a folga em
    cada eixo é (|o|−1)·passo, a mesma conta da margem por direção — por isso
    a mínima 3D nunca passa da menor das seis. Os deslocamentos vão em ordem
    crescente até o primeiro que encontra um voxel de fora; a ``cota`` (a
    menor margem por direção) limita a busca.
    """
    nucleo = dentro.copy()
    for eixo in range(3):
        for s in (1, -1):
            nucleo &= np.roll(dentro, s, axis=eixo)
    borda = np.argwhere(dentro & ~nucleo)
    raios = [int(cota / p) + 1 for p in passos]
    fora = np.pad(~externa, [(r, r) for r in raios], constant_values=True)
    base = np.ravel_multi_index((borda + raios).T, fora.shape)
    plano = fora.ravel()
    grades = np.meshgrid(*[np.arange(-r, r + 1) for r in raios], indexing="ij")
    desl = np.stack([g.ravel() for g in grades], axis=1)
    folga = np.maximum(np.abs(desl) - 1, 0) * np.asarray(passos)
    dist = np.sqrt((folga ** 2).sum(axis=1))
    ok = dist <= cota + 1e-9
    desl, dist = desl[ok], dist[ok]
    ordem = np.argsort(dist, kind="stable")
    passos_planos = np.array(fora.strides) // fora.itemsize
    for idx in ordem:
        if plano[base + int(desl[idx] @ passos_planos)].any():
            return float(dist[idx])
    return cota


def medir_margem(interna: Contornos, externa: Contornos, *,
                 resolucao_mm: float = 1.0,
                 espessura_mm: float | None = None) -> MargemMedida:
    """Mede a margem da ROI ``interna`` (CTV) até a ``externa`` (PTV).

    ``interna`` e ``externa`` são os contornos de cada ROI, um array ``(N, 3)``
    em mm por polígono, no sistema do paciente DICOM — o ``ContourData`` de
    cada item da ``ContourSequence``, já remodelado. Ler o RT Struct é de quem
    chama. ``espessura_mm`` só é preciso quando os contornos ocupam um plano
    só; senão sai do espaçamento dos planos.

    A precisão vem na saída: ``resolucao_mm`` em direita/esquerda e
    anterior/posterior, a espessura de corte em superior/inferior, e a
    diagonal do voxel na mínima 3D.
    """
    pi, pe = _poligonos(interna), _poligonos(externa)
    if not pi or not pe:
        raise ValueError("ROI sem contorno: não há o que medir")
    rede = _rede([pi, pe], resolucao_mm, espessura_mm)
    bi, be = _rasterizar(pi, rede), _rasterizar(pe, rede)
    # Um voxel de folga em volta: toda linha da grade termina FORA das duas.
    ini = tuple(min(a, b) - 1 for a, b in zip((bi.k0, bi.i0, bi.j0),
                                               (be.k0, be.i0, be.j0)))
    fim = tuple(max(a, b) + 1 for a, b in zip(bi.fim, be.fim))
    forma = tuple(f - i for i, f in zip(ini, fim))
    dentro, ext = _no_volume(bi, ini, forma), _no_volume(be, ini, forma)

    voxel_cm3 = rede.passo * rede.passo * rede.espessura / 1000.0
    n_dentro = int(dentro.sum())
    if n_dentro == 0:
        raise ValueError("a ROI interna não ocupa voxel nenhum nesta resolução")
    fracao_fora = float((dentro & ~ext).sum()) / n_dentro
    passos = (rede.espessura, rede.passo, rede.passo)

    planos = np.unique(np.rint((_zs(pi + pe) - rede.zref) / rede.espessura))
    # Um plano só: as duas ROIs não têm extensão em z, e "0 mm superior" seria
    # um número sem fonte — o físico leria que o CTV encosta na borda do PTV.
    um_plano = len(planos) == 1

    margens: dict[str, float | None] = {}
    vazadas: list[str] = []
    for nome in DIRECOES:
        eixo, sentido = _EIXO[nome]
        if um_plano and eixo == 0:
            margens[nome] = None
            continue
        margens[nome] = _margem_direcao(dentro, ext, eixo, sentido, passos[eixo])
        if margens[nome] is None:
            vazadas.append(nome)
    contida = fracao_fora == 0.0
    minima = (_minima_3d(dentro, ext, passos,
                         min(v for v in margens.values() if v is not None))
              if contida and not um_plano else None)

    p, e = rede.passo, rede.espessura
    precisao = {"direita": p, "esquerda": p, "anterior": p, "posterior": p,
                "superior": e, "inferior": e,
                "3d": math.sqrt(2 * p * p + e * e)}
    avisos = [f"superior/inferior: precisão de {e:.1f} mm, a espessura de "
              f"corte — a borda da ROI só existe de corte em corte"]
    if um_plano:
        avisos.insert(0, "contornos num plano só: sem margem superior/inferior "
                         "nem mínima 3D")
    # Plano dentro da extensão das duas sem contorno de nenhuma: ou a ROI tem
    # mesmo um salto, ou a TC mudou de espaçamento ali (2,5 mm num trecho de
    # 1,25). No segundo caso o plano vazio corta as duas ao meio, e a margem SI
    # e os volumes saem errados — o aviso diz onde olhar.
    vazios = int(planos[-1] - planos[0] + 1) - len(planos)
    if vazios:
        avisos.append(f"{vazios} plano(s) sem contorno de nenhuma das duas entre "
                      f"cortes contornados: se a TC muda de espaçamento ali, a "
                      f"margem superior/inferior e os volumes não valem")
    if not contida:
        onde = (f"sem margem em: {', '.join(vazadas)}" if vazadas else
                "a borda está dentro em toda direção, e o que sai fica num "
                "buraco ou recorte da externa")
        avisos.insert(0, f"{fracao_fora:.1%} do volume interno fica fora da "
                         f"externa; {onde}")
    return MargemMedida(
        margens_mm=MappingProxyType(margens),
        minima_3d_mm=minima,
        precisao_mm=MappingProxyType(precisao),
        resolucao_mm=p,
        espessura_corte_mm=e,
        contida=contida,
        fracao_fora=fracao_fora,
        volume_interna_cm3=n_dentro * voxel_cm3,
        volume_externa_cm3=int(ext.sum()) * voxel_cm3,
        avisos=tuple(avisos),
    )


def pares_por_contencao(rois: Mapping[str, Contornos], *,
                        limiar: float = 0.95, resolucao_mm: float = 2.0,
                        espessura_mm: float | None = None) -> list[ParCandidato]:
    """Pares (interna, externa) em que a interna cabe na externa.

    Critério só geométrico: fração do volume da interna dentro da externa
    ``>= limiar``, e a externa estritamente maior (duas cópias da mesma ROI
    não viram par). O NOME não entra na decisão — "CTV" e "PTV" são digitados
    à mão, e um par casado por parecença de nome mediria a margem entre as
    estruturas erradas em silêncio; o nome só aparece na saída, para a pessoa
    escolher. O BODY contém tudo e aparece como externa de quase todas: é par
    geométrico legítimo, e filtrar é de quem chama.

    Ordem: pela interna (como veio em ``rois``), e para cada uma da externa
    menor para a maior — a primeira é a que a envolve mais de perto.
    """
    polis = {nome: _poligonos(c) for nome, c in rois.items()}
    polis = {nome: p for nome, p in polis.items() if p}
    if not polis:
        return []
    rede = _rede(list(polis.values()), resolucao_mm, espessura_mm)
    blocos = {nome: _rasterizar(p, rede) for nome, p in polis.items()}
    contagem = {nome: int(b.m.sum()) for nome, b in blocos.items()}
    voxel_cm3 = rede.passo * rede.passo * rede.espessura / 1000.0
    pares: list[ParCandidato] = []
    for a, ba in blocos.items():
        if contagem[a] == 0:
            continue
        achados = []
        for b, bb in blocos.items():
            if b == a or contagem[b] <= contagem[a]:
                continue
            ini = [max(x, y) for x, y in zip((ba.k0, ba.i0, ba.j0),
                                             (bb.k0, bb.i0, bb.j0))]
            fim = [min(x, y) for x, y in zip(ba.fim, bb.fim)]
            if any(f <= i for i, f in zip(ini, fim)):
                continue
            sa = ba.m[ini[0] - ba.k0:fim[0] - ba.k0, ini[1] - ba.i0:fim[1] - ba.i0,
                      ini[2] - ba.j0:fim[2] - ba.j0]
            sb = bb.m[ini[0] - bb.k0:fim[0] - bb.k0, ini[1] - bb.i0:fim[1] - bb.i0,
                      ini[2] - bb.j0:fim[2] - bb.j0]
            fracao = int((sa & sb).sum()) / contagem[a]
            if fracao >= limiar:
                achados.append(ParCandidato(a, b, fracao, contagem[a] * voxel_cm3,
                                            contagem[b] * voxel_cm3))
        pares.extend(sorted(achados, key=lambda par: par.volume_externa_cm3))
    return pares
