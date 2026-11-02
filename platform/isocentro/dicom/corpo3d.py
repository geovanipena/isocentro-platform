"""Malha 3D do corpo do paciente a partir do contorno EXTERNAL.

O RT Struct guarda o corpo como uma pilha de polígonos axiais, e uma fatia tem
VÁRIOS polígonos sempre que o corpo se separa no plano axial: duas pernas, os
braços erguidos ao lado do tronco. É daí que vinha o problema.

Costurar contorno com contorno exige saber qual ponto de uma fatia corresponde a
qual ponto da seguinte, e essa correspondência não existe onde o corpo se divide:
o anel da pelve dá a volta nas DUAS coxas. Casá-lo com uma delas esticava a seção
inteira — o erro medido por ponto passava de ~1 mm (costura boa) para 85–166 mm
na junção, e saíam pratos horizontais atravessando as pernas e os ombros. Não é
questão de escolher melhor o par: o par não existe.

Por isso a superfície não vem mais de costura, e sim do VOLUME:

* ``_voxelizar`` preenche os contornos numa grade regular. Fatia sem contorno
  (o BODY do Monaco tem buracos de até 15 mm em z) herda a mais próxima.
* ``_faces_da_grade`` devolve um quad em cada fronteira cheio↔vazio. A topologia
  deixa de ser um problema a resolver: uma parte, duas ou cinco saem da mesma
  varredura, e a malha fecha sozinha (nenhuma aresta com uma face só).
* ``_suavizar_malha`` (laplaciano) tira o degrau do voxel e a ondulação corte a
  corte da contornagem, sem criar nem remover face.

A luz, o descarte do que está de costas e o PNG (com o cache) moram em
``desenho/corpo``, desde a R-58.

O TPS ainda mistura no BODY restos de contornagem que não são o paciente;
``_contornos_body`` corta por área absoluta e ``_sem_restos``, por área relativa
à seção do paciente.
"""

from __future__ import annotations

import numpy as np

# ── Extração de contornos ─────────────────────────────────────────────────────

_NOMES_BODY = {
    "BODY", "EXTERNAL", "BODY_CONTOUR", "SKIN", "CORPO", "CONTORNO", "EXTERNAL BODY",
    "EXTERNAL_CONTOUR", "EXT_BODY", "BODY_EXT", "BODY_SURFACE", "OUTER_CONTOUR",
}

# Área mínima de um polígono para ele contar como corpo (mm²; 100 = 1 cm²).
# O BODY do TPS vem salpicado de restos de contornagem: nos 10 pacientes de
# teste, 13% dos polígonos têm menos de 1 cm² — quase todos de 4 a 6 pontos e
# área ~0. Tudo abaixo de 1 cm² tem no máximo 34 pontos; acima, o mínimo é 28 e
# sobe rápido. Sem o filtro, cada resto vira um tubo na malha 3D (as "aletas")
# e pode virar a pele mais externa no cálculo do SSD.
_AREA_MIN_MM2 = 100.0


# Fração da seção VIZINHA (o maior polígono do próprio corte, ou o último corte
# mantido ao subir/descer em z) abaixo da qual um polígono é resto de
# contornagem, não anatomia — usada SÓ na malha 3D (ver _sem_restos).
_FRACAO_AREA_RESTO = 0.05


def _area_xy(pts: np.ndarray) -> float:
    """Área do polígono no plano XY (fórmula do shoelace), em mm²."""
    x, y = pts[:, 0], pts[:, 1]
    return abs(float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))) / 2.0


def _contornos_body(rs) -> dict[float, list[np.ndarray]]:
    """{z: [poly1, poly2, ...]} — TODOS os polígonos EXTERNAL por corte."""
    nums = {
        int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", ""))
        for o in getattr(rs, "RTROIObservationsSequence", [])
    }
    nomes_roi = {
        int(r.ROINumber): str(getattr(r, "ROIName", ""))
        for r in getattr(rs, "StructureSetROISequence", [])
    }

    # Candidatos por tipo DICOM, seguidos de fallback por nome — dedupados, tipo tem prioridade.
    externos_tipo = [n for n, t in nums.items() if t == "EXTERNAL"]
    externos_nome = [n for n, nome in nomes_roi.items() if nome.upper() in _NOMES_BODY]
    vistos = set(externos_tipo)
    candidatos = externos_tipo + [n for n in externos_nome if n not in vistos]

    if not candidatos:
        return {}

    # Percorre candidatos em ordem até encontrar um com geometria real.
    roi_contornos = list(getattr(rs, "ROIContourSequence", []))
    for alvo in candidatos:
        rc = next(
            (r for r in roi_contornos if int(r.ReferencedROINumber) == alvo), None
        )
        if rc is None:
            continue
        por_z: dict[float, list[np.ndarray]] = {}
        for c in getattr(rc, "ContourSequence", []):
            pts = np.array(c.ContourData, dtype=float).reshape(-1, 3)
            if len(pts) < 3 or _area_xy(pts) < _AREA_MIN_MM2:
                continue
            z = round(float(pts[0, 2]), 2)
            por_z.setdefault(z, []).append(pts)
        if por_z:
            for z in por_z:
                por_z[z].sort(key=len, reverse=True)
            return por_z
    return {}


def _sem_restos(cortes: dict[float, list[np.ndarray]]) -> dict[float, list[np.ndarray]]:
    """Tira os restos de contornagem da malha 3D: polígonos pequenos demais para
    serem o paciente.

    O limiar é sempre RELATIVO, nunca absoluto: 20 cm² é resto num tórax e é o
    topo do crânio num SRS. Nos planos do Monaco o BODY vem com uma cauda de
    caroços de 1 a 18 cm² acima dos ombros — o tubo esticava do tronco até eles
    e saíam pratos voando e um caroço de pé no topo do render.

    Mas relativo A QUÊ importa: comparar tudo com uma única medida do exame
    inteiro (era a mediana da maior área por corte) usa a seção MAIS LARGA como
    régua para o corpo todo. Num crânio-pescoço, em que os ombros puxam a
    mediana, isso jogava fora a calota do crânio — e ``_voxelizar`` a substituía
    pela seção vizinha que sobrou, achatando o topo da cabeça. São duas
    comparações locais no lugar dela:

    1. Dentro de um corte, contra o MAIOR polígono dele: pega o salpico ao lado
       do corpo, seja num tórax ou num crânio.
    2. Ao longo de z, andando para os dois lados a partir do corte mais largo
       (esse é o paciente, com certeza), contra o último corte MANTIDO — a régua
       acompanha o corpo afinando. Um afinamento anatômico é gradual e passa; a
       queda dos ombros para um caroço de 18 cm² não. Corte reprovado não vira
       régua nem interrompe a caminhada: uma fatia ruim no meio do corpo não
       leva embora tudo o que vem depois dela.

    Só a malha usa isto. O SSD continua com TODOS os polígonos
    (``_contornos_body``): lá um braço ou uma perna solta é justamente o que o
    raio pode encontrar primeiro.
    """
    if not cortes:
        return cortes
    maior = {z: max((_area_xy(p) for p in polys), default=0.0)
             for z, polys in cortes.items()}
    zs = sorted(cortes)
    inicio = max(zs, key=lambda z: maior[z])
    k0 = zs.index(inicio)

    manter = {inicio}
    for passo in (1, -1):
        ref = maior[inicio]
        k = k0 + passo
        while 0 <= k < len(zs):
            z = zs[k]
            if maior[z] >= ref * _FRACAO_AREA_RESTO:
                manter.add(z)
                ref = maior[z]
            k += passo

    limpo = {}
    for z in zs:
        if z not in manter:
            continue
        polys = [p for p in cortes[z]
                 if _area_xy(p) >= maior[z] * _FRACAO_AREA_RESTO]
        if polys:
            limpo[z] = polys
    return limpo


# ── Malha por voxel ──────────────────────────────────────────────────────────
#
# A costura de contornos exige correspondência ponto a ponto entre fatias, e ela
# não existe onde o corpo se divide (a pelve virando duas coxas, o braço saindo
# do tronco). Ali o anel de um lado dá a volta em DOIS do outro, e casá-lo com um
# deles estica a seção inteira: o erro medido por ponto ia de ~1 mm nas costuras
# boas para 85–166 mm nas junções, e o resultado saía como pratos horizontais
# atravessando as pernas e os ombros.
#
# Preencher o corpo numa grade e extrair a superfície resolve a topologia por
# construção: não existe "par" para achar, existe fronteira entre cheio e vazio.
# A malha sai fechada (cada aresta em exatamente duas faces) qualquer que seja o
# número de partes, e a suavização laplaciana tira o degrau do voxel.

# Aresta do voxel. 3 mm é o TETO: num corpo inteiro dá ~70k faces e resolve o
# relevo que a ficha mostra (crista ilíaca, virilha, mamilo); a 4 mm a silhueta
# já perde o contorno da coxa, e num crânio o rosto vira um ovo — some o nariz.
_PASSO_VOXEL_MM = 3.0
# ...e 2 mm é o PISO, para o que é pequeno. O custo do render não está na malha
# (1,2 s dos 6,4 s medidos num tórax) e sim no matplotlib, que desenha polígono a
# polígono: o tempo acompanha o nº de FACES, não o tamanho do paciente. Um crânio
# a 3 mm gasta só 17.534 faces e 1,8 s — sobra orçamento, e é justamente onde o
# detalhe fino aparece (nariz, órbita, queixo). A 2 mm ele sai com 39.026 faces
# em 3,3 s: ainda mais barato que o tórax, e com cara de rosto.
_PASSO_VOXEL_MIN_MM = 2.0
# Orçamento de faces por render — o do corpo inteiro a 3 mm, ou seja, o pior caso
# de HOJE. Nada fica mais lento que já era; o que for menor que isso ganha
# resolução até o piso.
_ORCAMENTO_FACES = 70_000
# Faces por mm² de caixa envolvente, por mm² de voxel. Medido, a razão fica em
# 0,85 (crânio) a 0,97 (tórax); usamos 1,0 — a superfície de um corpo não passa
# da caixa que o envolve. Estimar POR CIMA é o lado certo de errar: erra para
# passo mais grosso e o orçamento continua valendo.
_FACES_POR_AREA = 1.0


def _passo_adaptativo(cortes: dict) -> float:
    """Aresta do voxel para ``cortes``, pelo TAMANHO do corpo.

    Passo fixo trata um crânio como um tórax: no tórax 3 mm é o limite do que dá
    para pagar, e no crânio é grosso demais — o mesmo número de faces que num
    corpo inteiro cabe ali com o dobro da resolução. Escolhemos o passo que
    aproxima o nº de faces do orçamento, preso entre o piso e o teto.
    """
    xs = np.concatenate([p[:, 0] for polys in cortes.values() for p in polys])
    ys = np.concatenate([p[:, 1] for polys in cortes.values() for p in polys])
    zs = np.asarray(sorted(cortes), dtype=float)
    dx = float(xs.max() - xs.min()) or 1.0
    dy = float(ys.max() - ys.min()) or 1.0
    dz = float(zs[-1] - zs[0]) or 1.0
    area = 2.0 * (dx * dy + dy * dz + dx * dz)
    passo = float(np.sqrt(_FACES_POR_AREA * area / _ORCAMENTO_FACES))
    return min(_PASSO_VOXEL_MM, max(_PASSO_VOXEL_MIN_MM, passo))
# Passadas de suavização laplaciana e o passo de cada uma. 35 passadas tiram o
# degrau do voxel E a ondulação da contornagem; o volume da malha fica 3% ACIMA
# do volume dos contornos, ou seja, o que a suavização come é a sobra de meio
# voxel da extração, não o paciente. (Taubin, que alterna um passo de volta para
# não encolher, devolvia a alta frequência junto: a pele saía com anéis
# concêntricos, feito mapa topográfico.)
_SUAVIZA_MALHA = 35
_FATOR_LAPLACIANO = 0.5


def _voxelizar(cortes: dict, passo: float) -> tuple:
    """Preenche os contornos numa grade booleana (nz, ny, nx).

    Devolve ``(volume, origem)``, com ``origem`` = (x, y, z) do centro do voxel
    [0,0,0] em mm. Fatias sem contorno (o BODY do Monaco tem buracos de até
    15 mm em z) herdam a fatia contornada mais próxima — sem isso a malha ficaria
    com anéis abertos no meio do corpo.
    """
    from PIL import Image, ImageDraw

    zs = sorted(cortes)
    todos = np.vstack([p for polys in cortes.values() for p in polys])
    x0 = float(todos[:, 0].min()) - passo
    y0 = float(todos[:, 1].min()) - passo
    z0 = float(zs[0]) - passo
    nx = int(np.ceil((float(todos[:, 0].max()) + passo - x0) / passo)) + 1
    ny = int(np.ceil((float(todos[:, 1].max()) + passo - y0) / passo)) + 1
    nz = int(np.ceil((float(zs[-1]) + passo - z0) / passo)) + 1

    # Rasteriza cada fatia contornada uma única vez.
    por_fatia: dict[float, np.ndarray] = {}
    for z in zs:
        img = Image.new("1", (nx, ny), 0)
        d = ImageDraw.Draw(img)
        for poly in cortes[z]:
            xy = [(float((px - x0) / passo), float((py - y0) / passo))
                  for px, py in poly[:, :2]]
            d.polygon(xy, fill=1)
        por_fatia[z] = np.array(img, dtype=bool)

    zs_arr = np.asarray(zs, dtype=float)
    vol = np.zeros((nz, ny, nx), dtype=bool)
    for k in range(nz):
        zc = z0 + k * passo
        vol[k] = por_fatia[zs[int(np.abs(zs_arr - zc).argmin())]]
    return vol, (x0, y0, z0)


def _faces_da_grade(vol: np.ndarray, origem: tuple, passo: float) -> tuple:
    """Superfície do volume: um quad em cada fronteira cheio↔vazio.

    Devolve ``(vertices, quads)`` — ``vertices`` em mm (V,3) e ``quads`` os
    índices (F,4). Vértices são compartilhados entre faces vizinhas, o que é o
    que permite suavizar depois.
    """
    x0, y0, z0 = origem
    pad = np.zeros(np.array(vol.shape) + 2, dtype=bool)
    pad[1:-1, 1:-1, 1:-1] = vol
    dentro = pad[1:-1, 1:-1, 1:-1]

    verts: dict[tuple, int] = {}
    quads: list = []

    def _idx(i: int, j: int, k: int) -> int:
        """Índice do vértice no canto (i,j,k) da grade (unidades de voxel)."""
        v = verts.get((i, j, k))
        if v is None:
            v = len(verts)
            verts[(i, j, k)] = v
        return v

    # (deslocamento do vizinho, cantos do quad em coordenadas de canto)
    lados = [
        ((0, 0, 1), [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]),   # +x
        ((0, 0, -1), [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),  # -x
        ((0, 1, 0), [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),   # +y
        ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),  # -y
        ((1, 0, 0), [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),   # +z
        ((-1, 0, 0), [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]),  # -z
    ]
    for (dz, dy, dx), cantos in lados:
        viz = pad[1 + dz:pad.shape[0] - 1 + dz,
                  1 + dy:pad.shape[1] - 1 + dy,
                  1 + dx:pad.shape[2] - 1 + dx]
        kk, jj, ii = np.nonzero(dentro & ~viz)
        for k, j, i in zip(kk.tolist(), jj.tolist(), ii.tolist()):
            quads.append([_idx(i + cx, j + cy, k + cz) for cx, cy, cz in cantos])

    pts = np.empty((len(verts), 3), dtype=float)
    for (i, j, k), v in verts.items():
        pts[v] = (x0 + (i - 0.5) * passo, y0 + (j - 0.5) * passo,
                  z0 + (k - 0.5) * passo)
    return pts, np.asarray(quads, dtype=np.int64)


def _suavizar_malha(pts: np.ndarray, quads: np.ndarray,
                    iteracoes: int = _SUAVIZA_MALHA,
                    fator: float = _FATOR_LAPLACIANO) -> np.ndarray:
    """Suavização laplaciana: cada vértice caminha para a média dos vizinhos.

    Tira o degrau do voxel e a ondulação corte a corte da contornagem sem mexer
    na topologia — nenhuma face é criada ou removida, então a malha continua
    fechada.
    """
    if len(quads) == 0:
        return pts
    viz_a = quads.ravel()
    viz_b = np.roll(quads, -1, axis=1).ravel()
    i = np.concatenate([viz_a, viz_b])
    j = np.concatenate([viz_b, viz_a])
    grau = np.maximum(np.bincount(i, minlength=len(pts)), 1).astype(float)
    for _ in range(iteracoes):
        soma = np.empty_like(pts)
        for eixo in range(3):
            soma[:, eixo] = np.bincount(i, weights=pts[j, eixo], minlength=len(pts))
        pts = pts + fator * (soma / grau[:, None] - pts)
    return pts


def malha_do_corpo(cortes: dict, passo: float = _PASSO_VOXEL_MM) -> tuple:
    """``(pontos, quads)`` da superfície do corpo, a partir dos contornos.

    Ver o comentário da seção: preenche, extrai a fronteira e suaviza.
    """
    vol, origem = _voxelizar(cortes, passo)
    pts, quads = _faces_da_grade(vol, origem, passo)
    if len(quads) == 0:
        return pts, quads
    return _suavizar_malha(pts, quads), quads
