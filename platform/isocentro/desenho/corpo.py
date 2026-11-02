"""O corpo 3D desenhado: luz, visada e o PNG, com cache.

A malha vem de ``dicom/corpo3d`` (voxelizar, extrair a fronteira, suavizar);
daqui sai a imagem. Separado na R-58 (corte 3), para a malha poder ir para
``rt/`` sem matplotlib nem disco.

* ``_sombrear_malha`` acende cada face pela normal MÉDIA dos seus vértices, o que
  dá o mesmo efeito do sombreamento Gouraud sem depender de a malha ser grade.
* ``_faces_visiveis`` joga fora o que está de costas para a câmera: o matplotlib
  não tem z-buffer, e sem isso a parede interna do corpo era desenhada por cima
  da externa e vazava para fora da silhueta.
"""

from __future__ import annotations

import io
import threading

import numpy as np

from isocentro.dicom import corpo3d

# Cor base da pele e direção da luz.
# Bege bem claro: a superfície tem que sair branca na folha, não cinza-médio.
_BASE = (0.92, 0.90, 0.87)
_LUZ = (-0.3, -0.5, 0.8)

# Iluminação lambertiana pura (fosca). O ângulo entre a principal e a de
# preenchimento é o que decide se o orçamento abaixo é real: a 117° (como já
# esteve) o preenchimento NUNCA soma numa face iluminada — o pico caía para
# ambiente+difusa e o corpo imprimia cinza. A 67° ele entra de fato, então o pico
# chega a 0,98 e a sombra fica em 0,52: mais branco que a versão de ambiente 0,6
# E com mais relevo (0,46 de contraste contra 0,40 dela).
_LUZ_PREENCH = (0.5, 0.2, 0.75)
_AMBIENTE = 0.52
_DIFUSA = 0.40
_PREENCHIMENTO = 0.12


# ── Iluminação ────────────────────────────────────────────────────────────────

def _normais(faces: list) -> np.ndarray:
    """Normais unitárias das faces, já apontando para FORA do corpo.

    A malha tem orientação consistente por construção: ``_faces_da_grade`` emite
    os quatro cantos de cada quad na ordem que deixa o produto vetorial dos dois
    primeiros lados apontando para o lado VAZIO da fronteira. Não depende de
    nenhuma heurística de "eixo do corpo" — e é isso que importa, porque orientar
    pelo eixo errava exatamente onde a superfície é côncava (a fenda entre as
    mamas, a face interna de um braço, a virilha).
    """
    v = np.array([f[:3] for f in faces], dtype=float)          # (N, 3, 3)
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    norma = np.linalg.norm(n, axis=1, keepdims=True)
    return np.divide(n, norma, out=np.zeros_like(n), where=norma > 1e-9)


def _cores_da_luz(normais: np.ndarray) -> list:
    """Cor de cada face a partir da sua normal — lambertiano puro, sem especular.

    Uma luz principal dá o relevo (nariz/órbitas/queixo) e uma de preenchimento,
    fraca e vinda do lado oposto, levanta a sombra: sem ela o lado escuro fecha
    num tom chapado e o volume some ali. É o esquema de duas luzes de estúdio, que
    lê como objeto real; a componente ambiente continua abrindo o conjunto.
    """
    base_a = np.array(_BASE, dtype=float)
    principal = np.array(_LUZ, dtype=float)
    principal /= np.linalg.norm(principal)
    preench = np.array(_LUZ_PREENCH, dtype=float)
    preench /= np.linalg.norm(preench)

    dif = np.clip(normais @ principal, 0.0, None)
    fill = np.clip(normais @ preench, 0.0, None)
    inten = _AMBIENTE + _DIFUSA * dif + _PREENCHIMENTO * fill
    rgb = np.clip(inten[:, None] * base_a, 0, 1)
    return [tuple(c) + (1.0,) for c in rgb]


def _faces_visiveis(faces: list, elev: float, azim: float) -> np.ndarray:
    """Máscara das faces que encaram a câmera (back-face culling na CPU).

    O matplotlib 3D não tem z-buffer: ele ordena as faces pela profundidade média
    e desenha nessa ordem. Perto das extremidades do volume isso põe a parede de
    DENTRO do corpo na frente da de fora, e o interior aparecia como uma aba plana
    vazando da silhueta — embaixo do queixo no crânio, em volta da base no tórax.
    Descartar o que está de costas resolve na origem (e corta ~metade das faces).

    A direção da câmera segue a convenção do ``view_init``; os eixos do render são
    isotrópicos (``set_box_aspect`` com os ptp reais), então dá para comparar
    normal e visada direto nas coordenadas do paciente.
    """
    e, a = np.radians(elev), np.radians(azim)
    camera = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    return _normais(faces) @ camera > 0


# ── Ponto de entrada ─────────────────────────────────────────────────────────

def renderizar_corpo(rs, elev: float = 10, azim: float = -30,
                     passo: float | None = None) -> bytes | None:
    """Gera PNG (bytes) do corpo 3D. Retorna None se não houver EXTERNAL.

    Fundo TRANSPARENTE: o mesmo PNG serve o app (painel preto atrás → 3D no
    preto) e o PDF (página branca atrás → 3D no branco), sem precisar de dois
    renders nem cache por cor.

    ``passo``: aresta do voxel em mm. O padrão acompanha o tamanho do corpo (ver
    ``_passo_adaptativo``) — um crânio sai mais fino que um corpo inteiro, pelo
    mesmo custo de render. Tela e ficha usam o MESMO passo: o que se vê girando
    é o que sai impresso.

    **Com cache** (ver ``_CACHE`` mais abaixo): o mesmo contorno, com os mesmos
    parâmetros e o mesmo código, devolve os MESMOS bytes sem desenhar de novo.
    """
    cortes = corpo3d._sem_restos(corpo3d._contornos_body(rs))
    if len(cortes) < 3:
        return None
    return _com_cache(cortes, elev, azim, passo)


def _desenhar(cortes: dict, elev: float, azim: float,
              passo: float | None) -> bytes | None:
    """O render de fato — sem cache. Ver ``renderizar_corpo``."""
    pts, quads = corpo3d.malha_do_corpo(
        cortes, passo or corpo3d._passo_adaptativo(cortes))
    if len(quads) == 0:
        return None
    all_faces = [f.tolist() for f in pts[quads]]
    all_cors = _sombrear_malha(pts, quads)

    # ── Descarta o que está de costas para a câmera (ver _faces_visiveis): sem
    # isso a parede interna do corpo era desenhada por cima e vazava da silhueta.
    vis = _faces_visiveis(all_faces, elev, azim)
    all_faces = [f for f, v in zip(all_faces, vis) if v]
    all_cors = [c for c, v in zip(all_cors, vis) if v]
    if not all_faces:
        return None

    # ── Renderização matplotlib ───────────────────────────────────────────────
    # ``Figure`` direto, NÃO ``pyplot``: este render roda numa thread de fundo
    # (ver ``gui._Render3D``) enquanto a interface pode estar gerando o DVH na
    # thread principal. O pyplot mantém um registro GLOBAL de figuras, e as duas
    # threads mexendo nele ao mesmo tempo corrompiam a estrutura e derrubavam o
    # processo inteiro com access violation — não uma exceção Python, então o
    # try/except do worker não pegava. A API orientada a objetos não tem estado
    # global e é a forma que o próprio matplotlib recomenda fora do main thread.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = Figure(figsize=(4.0, 5.2), dpi=200)
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)                 # fundo da figura transparente
    ax = fig.add_subplot(111, projection="3d")
    ax.patch.set_alpha(0.0)                   # fundo dos eixos transparente

    # Borda da MESMA cor da face (não "none"): com as faces de trás descartadas,
    # o antialiasing deixava passar o fundo pela fresta entre faces vizinhas e a
    # pele ganhava textura de escamas. A borda fina sela essas junções.
    malha = Poly3DCollection(all_faces, alpha=1.0, facecolors=all_cors,
                             edgecolors=all_cors, linewidths=0.35)
    ax.add_collection3d(malha)

    todos_pts = pts
    ax.set_xlim(todos_pts[:, 0].min(), todos_pts[:, 0].max())
    ax.set_ylim(todos_pts[:, 1].min(), todos_pts[:, 1].max())
    ax.set_zlim(todos_pts[:, 2].min(), todos_pts[:, 2].max())
    ax.set_box_aspect((
        np.ptp(todos_pts[:, 0]),
        np.ptp(todos_pts[:, 1]),
        np.ptp(todos_pts[:, 2]),
    ))

    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    fig.tight_layout(pad=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    # Sem ``plt.close``: a figura não está em registro nenhum, então sai da
    # memória sozinha quando esta função retorna.
    return buf.getvalue()


# ── Cache do render ──────────────────────────────────────────────────────────
#
# O render custa de 14 a 22 s por plano na estação (medido em 07/10/2026, num
# caso de quatro planos com quatro TCs), e roda NA THREAD DA TELA quando a
# prévia da ficha é montada. Era pago de novo em cada passo — prévia,
# Impressão, Visualizar — e mais de uma vez por ficha quando dois planos têm o
# mesmo RTSTRUCT: no caso medido, cinco renders e 87 s de janela "Não
# respondendo" no clique da Documentação PRONTA. Da cadeira, o programa travou.
#
# O render é função PURA dos contornos, dos parâmetros e do código: guardar o
# PNG não muda um pixel do que vai para o papel. Por isso a chave é a impressão
# digital EXATA dessas três coisas — os pontos de cada polígono do BODY já
# limpo, o ângulo e o passo, e o próprio código deste módulo (o bytecode das
# funções e as constantes de iluminação e malha). Mudou a luz, a malha ou o
# filtro de restos, a chave muda e o PNG antigo deixa de valer sozinho, sem
# ninguém precisar lembrar de "limpar o cache".
#
# Memória para todo render; DISCO só para o ângulo da ficha (o padrão): o
# visualizador gira o corpo, e um arquivo por ângulo encheria a pasta de PNG
# que ninguém vai pedir de novo. No disco, o caso reaberto amanhã — ou a
# Documentação preparada pela automação — já sai sem esperar.

ENV_CACHE = "ISOCENTRO_CACHE_3D"
_MAX_MEMORIA = 32
_MAX_DISCO = 300
_ANGULO_DA_FICHA = (10, -30)
_memoria: dict = {}
_em_curso: dict = {}
_assinatura: dict = {}
_trava_cache = threading.Lock()


def _resumo_do_codigo(codigo, h) -> None:
    """Alimenta ``h`` com o bytecode e as constantes de ``codigo``, recursivo.

    ``repr`` de um code object traz endereço de memória — muda a cada execução e
    o cache de disco nunca bateria. Por isso as funções internas descem pelo
    próprio bytecode, e só o que é valor simples entra por ``repr``.
    """
    import types

    h.update(codigo.co_code)
    for c in codigo.co_consts:
        if isinstance(c, types.CodeType):
            _resumo_do_codigo(c, h)
        else:
            h.update(repr(c).encode("utf-8", "replace"))


def _assinatura_do_codigo() -> str:
    """Impressão digital do que DESENHA: funções e constantes deste módulo
    E do ``dicom/corpo3d``, que faz a malha.

    São os dois porque o PNG depende dos dois: com a assinatura só deste, mudar
    o passo do voxel ou o filtro de restos deixaria no disco o PNG da malha
    antiga — e é ele que vai para o papel.

    Calculada uma vez por processo (``_assinatura``); quem muda constante em
    teste limpa o dicionário para ela ser refeita.
    """
    if "valor" in _assinatura:
        return _assinatura["valor"]
    import hashlib
    import sys
    import types

    import matplotlib

    h = hashlib.sha1(matplotlib.__version__.encode())
    for modulo in (sys.modules[__name__], corpo3d):
        h.update(modulo.__name__.encode())
        for nome, valor in sorted(vars(modulo).items()):
            if (isinstance(valor, types.FunctionType)
                    and valor.__module__ == modulo.__name__):
                h.update(nome.encode())
                _resumo_do_codigo(valor.__code__, h)
            elif (nome.startswith("_") and nome[1:2].isupper()
                  and isinstance(valor, (int, float, str, tuple, frozenset, set))):
                h.update(f"{nome}={sorted(valor) if isinstance(valor, (set, frozenset)) else valor!r}"
                         .encode())
    _assinatura["valor"] = h.hexdigest()
    return _assinatura["valor"]


def _chave(cortes: dict, elev, azim, passo) -> str:
    import hashlib

    h = hashlib.sha1(_assinatura_do_codigo().encode())
    h.update(repr((float(elev), float(azim), passo)).encode())
    for z in sorted(cortes):
        h.update(repr(z).encode())
        for poly in cortes[z]:
            h.update(np.ascontiguousarray(poly, dtype=float).tobytes())
    return h.hexdigest()


def _pasta_cache():
    from pathlib import Path

    from isocentro import raiz
    from isocentro.dados import ambiente

    escolhida = ambiente.ler(ENV_CACHE)
    return Path(escolhida) if escolhida else raiz.pasta_do_app() / "cache_corpo3d"


def _no_disco(elev, azim) -> bool:
    return (float(elev), float(azim)) == tuple(map(float, _ANGULO_DA_FICHA))


def _ler_disco(chave: str) -> bytes | None:
    try:
        return (_pasta_cache() / f"{chave}.png").read_bytes()
    except OSError:
        return None


def _gravar_disco(chave: str, png: bytes) -> None:
    """Grava e poda os mais antigos. Falha aqui nunca derruba o render."""
    try:
        pasta = _pasta_cache()
        pasta.mkdir(parents=True, exist_ok=True)
        provisorio = pasta / f"{chave}.tmp"
        provisorio.write_bytes(png)
        provisorio.replace(pasta / f"{chave}.png")
        arquivos = sorted(pasta.glob("*.png"), key=lambda p: p.stat().st_mtime)
        for velho in arquivos[:-_MAX_DISCO]:
            velho.unlink(missing_ok=True)
    except OSError:
        pass


def _com_cache(cortes: dict, elev, azim, passo) -> bytes | None:
    """Devolve o PNG guardado ou desenha UMA vez — inclusive quando duas threads
    (o visualizador e a ficha) pedem o mesmo render ao mesmo tempo: a segunda
    espera a primeira em vez de pagar o render de novo."""
    chave = _chave(cortes, elev, azim, passo)
    trava = _trava_cache
    with trava:
        if chave in _memoria:
            return _memoria[chave]
        evento = _em_curso.get(chave)
        dono = evento is None
        if dono:
            evento = _em_curso[chave] = threading.Event()
    if not dono:
        evento.wait()
        with trava:
            if chave in _memoria:
                return _memoria[chave]
        return _desenhar(cortes, elev, azim, passo)
    try:
        png = _ler_disco(chave) if _no_disco(elev, azim) else None
        if png is None:
            png = _desenhar(cortes, elev, azim, passo)
            if png and _no_disco(elev, azim):
                _gravar_disco(chave, png)
        with trava:
            if png:
                _memoria[chave] = png
                while len(_memoria) > _MAX_MEMORIA:
                    _memoria.pop(next(iter(_memoria)))
        return png
    finally:
        with trava:
            _em_curso.pop(chave, None)
        evento.set()


def _sombrear_malha(pts: np.ndarray, quads: np.ndarray) -> list:
    """Cor de cada face pela normal MÉDIA dos seus vértices.

    A normal de vértice é a média das faces que o tocam, então faces vizinhas
    recebem cores próximas e o degrau do voxel some da luz também — é o mesmo
    efeito que ``_sombrear_grade`` dá nas seções regulares, aqui sem depender de
    a malha ser uma grade.
    """
    v = pts[quads]
    n_face = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n_vert = np.zeros_like(pts)
    for canto in range(quads.shape[1]):
        for eixo in range(3):
            n_vert[:, eixo] += np.bincount(quads[:, canto], weights=n_face[:, eixo],
                                           minlength=len(pts))
    n_vert /= np.maximum(np.linalg.norm(n_vert, axis=1, keepdims=True), 1e-12)
    n_suave = n_vert[quads].mean(axis=1)
    n_suave /= np.maximum(np.linalg.norm(n_suave, axis=1, keepdims=True), 1e-12)
    return _cores_da_luz(n_suave)
